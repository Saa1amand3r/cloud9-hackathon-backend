from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests

from .config import CacheConfig, cache_config_from_env


@dataclass
class GridGraphQLClient:
    api_key: str
    timeout_s: int = 30
    cache: Optional[CacheConfig] = None

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "accept": "application/json",
            }
        )
        if self.cache is None:
            self.cache = cache_config_from_env()

    def _cache_path(self, url: str, gql: str, variables: Optional[Dict[str, Any]]) -> Path:
        assert self.cache is not None
        key_src = json.dumps({"url": url, "gql": gql, "variables": variables or {}}, sort_keys=True)
        digest = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
        return self.cache.base_dir / f"{digest}.json"

    def query(
        self,
        url: str,
        gql: str,
        variables: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        backoff_s: float = 0.6,
    ) -> Dict[str, Any]:
        payload = {"query": gql, "variables": variables or {}}
        cache = self.cache
        if cache and cache.enabled:
            path = self._cache_path(url, gql, variables)
            if path.exists():
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)

        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout_s)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(backoff_s * (attempt + 1))
                    continue

                resp.raise_for_status()
                body = resp.json()
                if "errors" in body:
                    errors = body["errors"]
                    # Check for rate limit errors and retry
                    is_rate_limit = any(
                        e.get("extensions", {}).get("errorDetail") == "ENHANCE_YOUR_CALM"
                        or e.get("extensions", {}).get("errorType") == "UNAVAILABLE"
                        or "rate limit" in e.get("message", "").lower()
                        for e in errors
                    )
                    if is_rate_limit and attempt < retries - 1:
                        time.sleep(backoff_s * (attempt + 2))  # Longer backoff for rate limits
                        continue
                    raise RuntimeError("GraphQL errors: " + json.dumps(errors, indent=2))
                if "data" not in body:
                    raise RuntimeError("Unexpected response shape: " + json.dumps(body, indent=2))

                data = body["data"]
                if cache and cache.enabled:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("w", encoding="utf-8") as f:
                        json.dump(data, f)
                return data
            except Exception as exc:
                last_err = exc
                time.sleep(backoff_s * (attempt + 1))

        raise RuntimeError(f"Failed after {retries} attempts. Last error: {last_err}")


def query_across_endpoints(
    client: GridGraphQLClient,
    urls: List[str],
    gql: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    last_err: Optional[Exception] = None
    for url in urls:
        try:
            return url, client.query(url, gql, variables)
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"All endpoints failed. Last error: {last_err}")


def paginate_connection(
    fetch_page_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    variables: Dict[str, Any],
    connection_path: List[str],
    page_size: int,
    after_key: str = "after",
) -> Iterable[Dict[str, Any]]:
    """
    Yield nodes across paginated GraphQL connections.

    fetch_page_fn receives variables dict and returns the GraphQL data dict.
    connection_path is the path to the connection object (e.g., ["tournaments"]).
    """
    cursor: Optional[str] = None
    while True:
        vars_with_after = dict(variables)
        vars_with_after["first"] = page_size
        vars_with_after[after_key] = cursor

        data = fetch_page_fn(vars_with_after)
        conn = data
        for key in connection_path:
            conn = conn.get(key, {})

        edges = conn.get("edges") or []
        for edge in edges:
            node = edge.get("node") or {}
            if node:
                yield node

        page_info = conn.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break
