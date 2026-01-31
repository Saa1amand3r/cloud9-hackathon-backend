from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


CENTRAL_DATA_URLS: List[str] = [
    "https://api.grid.gg/central-data/graphql",
    "https://api-op.grid.gg/central-data/graphql",
]

SERIES_STATE_URLS: List[str] = [
    "https://api.grid.gg/live-data-feed/series-state/graphql",
    "https://api-op.grid.gg/live-data-feed/series-state/graphql",
]

DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool
    base_dir: Path


def cache_config_from_env() -> CacheConfig:
    enabled = os.environ.get("GRID_CACHE", "0").lower() in {"1", "true", "yes"}
    base_dir = Path(os.environ.get("GRID_CACHE_DIR", ".cache/grid"))
    return CacheConfig(enabled=enabled, base_dir=base_dir)
