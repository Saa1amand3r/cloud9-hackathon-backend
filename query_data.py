#!/usr/bin/env python3
"""
GRID Central Data / Series State quick query script (hackathon-ready)


What this fixes vs your previous version:
- Works even when "last 30 days" returns 0 (Open Access often has older archived data)
- Auto-discovers the newest available series date in the dataset, then queries a window around it
- Tries BOTH hosts you mentioned (api.grid.gg then api-op.grid.gg), picks the first that works
- Optional .env loading (python-dotenv)
- Clear error printing + helpful console output

Usage:
  export GRID_API_KEY="..."
  # or put GRID_API_KEY=... in .env and `pip install python-dotenv`

  pip install requests python-dotenv
  python query_data.py
"""

import os
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List, Tuple

import requests

# Optional: load from .env if python-dotenv is installed
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# --- Endpoints to try (you mentioned these) ---
CENTRAL_DATA_URLS = [
    "https://api.grid.gg/central-data/graphql",
    "https://api-op.grid.gg/central-data/graphql",
]

SERIES_STATE_URLS = [
    "https://api.grid.gg/live-data-feed/series-state/graphql",
    "https://api-op.grid.gg/live-data-feed/series-state/graphql",
]


class GridGraphQLClient:
    def __init__(self, api_key: str, timeout_s: int = 30):
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "accept": "application/json",
            }
        )

    def query(
        self,
        url: str,
        gql: str,
        variables: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        payload = {"query": gql, "variables": variables or {}}

        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                r = self.session.post(url, json=payload, timeout=self.timeout_s)

                # retry on transient errors / rate limits
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(0.8 * (attempt + 1))
                    continue

                r.raise_for_status()
                resp = r.json()

                if "errors" in resp:
                    raise RuntimeError("GraphQL errors:\n" + json.dumps(resp["errors"], indent=2))

                if "data" not in resp:
                    raise RuntimeError(f"Unexpected response shape:\n{json.dumps(resp, indent=2)}")

                return resp["data"]

            except Exception as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Failed after {retries} attempts. Last error: {last_err}")


def try_query_across_endpoints(
    client: GridGraphQLClient,
    urls: List[str],
    gql: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Try the same query against multiple endpoints; return the first that works."""
    last_err: Optional[Exception] = None
    for url in urls:
        try:
            data = client.query(url, gql, variables)
            return url, data
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All endpoints failed. Last error: {last_err}")


def iso_z(dt: datetime) -> str:
    """Format datetime as ISO-8601 Z string like 2026-01-28T12:34:56Z"""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_z(s: str) -> datetime:
    """Parse ISO-8601 Z timestamps like 2024-01-13T16:00:00Z"""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def print_series(edges: List[dict], limit: int = 5) -> None:
    for edge in edges[:limit]:
        node = edge["node"]
        teams = node.get("teams") or []
        team_names: List[str] = []
        for t in teams:
            base = t.get("baseInfo") or {}
            name = base.get("name")
            if name:
                team_names.append(name)

        tournament = (node.get("tournament") or {}).get("name")
        print(f"- {node.get('id')} | {node.get('startTimeScheduled')} | {tournament} | {', '.join(team_names)}")


# --- Queries ---
# 1) Time-window series query (your schema expects Strings for gte/lte)
ALL_SERIES_QUERY = """
query AllSeries($gte: String!, $lte: String!) {
  allSeries(
    filter: { startTimeScheduled: { gte: $gte, lte: $lte } }
    orderBy: StartTimeScheduled
  ) {
    edges {
      node {
        id
        startTimeScheduled
        tournament { id name }
        teams { baseInfo { id name } }
      }
    }
  }
}
"""

# 2) Probe: fetch a small batch (used to determine "newest available" if needed)
PROBE_SERIES_QUERY = """
query ProbeSeries {
  allSeries(orderBy: StartTimeScheduled) {
    edges {
      node {
        id
        startTimeScheduled
        tournament { name }
        teams { baseInfo { name } }
      }
    }
  }
}
"""

# 3) "Latest" query attempt (some schemas support a Desc order; if yours doesn't, we fall back)
LATEST_SERIES_QUERY = """
query LatestSeries {
  allSeries(orderBy: StartTimeScheduledDesc) {
    edges {
      node {
        id
        startTimeScheduled
        tournament { name }
        teams { baseInfo { name } }
      }
    }
  }
}
"""

SERIES_STATE_QUERY = """
query SeriesState($id: ID!) {
  seriesState(id: $id) {
    startedAt
    finished
    teams {
      won
      score
      kills
      deaths
      # if players exist in your schema, keep this; otherwise remove
      players { kills deaths }
    }
  }
}
"""


def main() -> None:
    api_key = os.environ.get("GRID_API_KEY")
    if not api_key:
        raise SystemExit(
            "GRID_API_KEY not found.\n"
            "Fix:\n"
            "  export GRID_API_KEY='...'\n"
            "or put GRID_API_KEY=... in a .env file and `pip install python-dotenv`.\n"
        )

    client = GridGraphQLClient(api_key)

    # Step A: Discover newest available series date in this dataset
    newest_dt: Optional[datetime] = None

    # Try a "latest" query (may fail depending on schema)
    try:
        latest_url, latest_data = try_query_across_endpoints(client, CENTRAL_DATA_URLS, LATEST_SERIES_QUERY, None)
        latest_edges = latest_data.get("allSeries", {}).get("edges", []) or []
        if latest_edges:
            newest_dt = parse_z(latest_edges[0]["node"]["startTimeScheduled"])
            print(f"[Latest] endpoint OK: {latest_url}")
    except Exception:
        # ignore and fall back to probe
        newest_dt = None

    # Fall back: use probe (works even if Desc isn't supported)
    if newest_dt is None:
        probe_url, probe_data = try_query_across_endpoints(client, CENTRAL_DATA_URLS, PROBE_SERIES_QUERY, None)
        probe_edges = probe_data.get("allSeries", {}).get("edges", []) or []
        if not probe_edges:
            raise SystemExit("Probe returned 0 series. This key/endpoint may not have any available data.")
        newest_dt = max(parse_z(e["node"]["startTimeScheduled"]) for e in probe_edges)
        print(f"[Probe] endpoint OK: {probe_url}")

        # Show a few probe samples for sanity
        print("Probe returned series (showing up to 5):")
        print_series(probe_edges, limit=5)
        print()

    assert newest_dt is not None
    print(f"Newest series timestamp available: {iso_z(newest_dt)}")

    # Step B: Query a window around the newest date (default: 14 days back)
    window_days_back = int(os.environ.get("GRID_WINDOW_DAYS", "14"))
    gte = iso_z(newest_dt - timedelta(days=window_days_back))
    lte = iso_z(newest_dt + timedelta(days=1))

    print(f"Querying window: {gte} -> {lte}")

    central_url, data = try_query_across_endpoints(
        client,
        CENTRAL_DATA_URLS,
        ALL_SERIES_QUERY,
        {"gte": gte, "lte": lte},
    )

    edges = data.get("allSeries", {}).get("edges", []) or []
    print(f"[Central Data] endpoint OK: {central_url}")
    print(f"Got {len(edges)} series in window.\n")

    if not edges:
        print("No series found in computed window (unexpected). Try increasing GRID_WINDOW_DAYS, e.g.:")
        print("  GRID_WINDOW_DAYS=90 python query_data.py")
        return

    print("Sample series (up to 10):")
    print_series(edges, limit=10)


    series_id = edges[0]["node"]["id"]
    ss_url, ss_data = try_query_across_endpoints(
        client, SERIES_STATE_URLS, SERIES_STATE_QUERY, {"id": series_id}
    )
    print(f"\n[Series State] endpoint OK: {ss_url}")
    print(json.dumps(ss_data, indent=2))


    # Optional next step: query seriesState for the first series ID (commented)
    # Uncomment once you want to start pulling per-series stats.
    #
    # series_id = edges[0]["node"]["id"]
    # SERIES_STATE_QUERY = """
    # query SeriesState($id: ID!) {
    #   seriesState(id: $id) {
    #     startedAt
    #     finished
    #     teams { won score kills deaths }
    #   }
    # }
    # """
    # ss_url, ss_data = try_query_across_endpoints(
    #     client, SERIES_STATE_URLS, SERIES_STATE_QUERY, {"id": series_id}
    # )
    # print(f"\n[Series State] endpoint OK: {ss_url}")
    # print(json.dumps(ss_data, indent=2))


if __name__ == "__main__":
    main()

