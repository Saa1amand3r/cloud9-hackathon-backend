from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

from .grid_ingest import (
    FetchMeta,
    fetch_series_for_matchup,
    raw_records_from_json,
    raw_records_to_json,
)
from .normalize import normalize_records
from .report import build_report
from .render import render_text


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated scouting report generator")
    parser.add_argument("--title", required=True, help="Game title (lol or valorant)")
    parser.add_argument("--team", required=True, help="Our team name")
    parser.add_argument("--opponent", required=True, help="Opponent team name")
    parser.add_argument("--window-days", type=int, required=True, help="Days back to include")
    parser.add_argument("--tournament-filter", default=None, help="Optional tournament name filter")
    parser.add_argument("--save-raw", default=None, help="Path to save raw series JSON")
    parser.add_argument("--save-normalized", default=None, help="Path to save normalized games JSON")
    parser.add_argument("--output", default=None, help="Path to output report JSON/text")
    parser.add_argument(
        "--output-format", choices=["json", "text"], default="json", help="Output format"
    )
    parser.add_argument("--team-id", default=None, help="Override team id")
    parser.add_argument("--opponent-id", default=None, help="Override opponent id")
    parser.add_argument("--from-raw", default=None, help="Load raw JSON instead of querying GRID")
    parser.add_argument("--cache", action="store_true", help="Enable on-disk cache")
    parser.add_argument("--debug", action="store_true", help="Print debug logs")
    return parser.parse_args()


def main() -> None:
    _load_env()
    args = _parse_args()

    if args.cache:
        os.environ["GRID_CACHE"] = "1"

    records = []
    meta: Optional[FetchMeta] = None

    if args.from_raw:
        with open(args.from_raw, "r", encoding="utf-8") as f:
            raw = json.load(f)
        records = raw_records_from_json(raw.get("records") or raw)
        meta_dict = raw.get("meta") or {}
        meta = FetchMeta(
            team_name=meta_dict.get("team_name") or args.team,
            opponent_name=meta_dict.get("opponent_name") or args.opponent,
            team_id=meta_dict.get("team_id") or (args.team_id or ""),
            opponent_id=meta_dict.get("opponent_id") or (args.opponent_id or ""),
            title=meta_dict.get("title") or args.title,
            window_gte=meta_dict.get("window_gte") or "",
            window_lte=meta_dict.get("window_lte") or "",
            series_found=meta_dict.get("series_found") or 0,
            series_analyzed=meta_dict.get("series_analyzed") or len(records),
        )
    else:
        api_key = os.environ.get("GRID_API_KEY")
        if not api_key:
            raise SystemExit(
                "GRID_API_KEY not found. Set it in your shell or .env file before running."
            )
        records, meta = fetch_series_for_matchup(
            api_key=api_key,
            title=args.title,
            team_name=args.team,
            opponent_name=args.opponent,
            window_days_back=args.window_days,
            tournament_name_filter=args.tournament_filter,
            team_id_override=args.team_id,
            opponent_id_override=args.opponent_id,
            debug=args.debug,
        )

    if args.save_raw:
        _write_json(args.save_raw, {"meta": meta.__dict__ if meta else {}, "records": raw_records_to_json(records)})

    if not meta:
        raise SystemExit("Missing meta data; cannot build report.")

    games = normalize_records(records, meta.team_id, meta.opponent_id)

    if args.save_normalized:
        _write_json(args.save_normalized, [g.__dict__ for g in games])

    report = build_report(games, meta)

    if args.output_format == "json":
        output_text = json.dumps(report, indent=2)
    else:
        output_text = render_text(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
