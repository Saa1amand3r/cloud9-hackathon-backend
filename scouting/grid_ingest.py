from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import CENTRAL_DATA_URLS, DEFAULT_PAGE_SIZE, SERIES_STATE_URLS
from .grid_client import GridGraphQLClient, paginate_connection, query_across_endpoints
from .grid_queries import (
    ALL_SERIES_QUERY,
    SERIES_STATE_QUERY_BASIC,
    SERIES_STATE_QUERY_CHARACTER,
    TEAMS_QUERY_BASIC,
    TEAMS_QUERY_EXTENDED,
    TITLES_QUERY,
    TOURNAMENTS_QUERY,
)


@dataclass
class RawSeriesRecord:
    series_id: str
    start_time: str
    tournament: Dict[str, Any]
    teams: List[Dict[str, Any]]
    series_state: Dict[str, Any]


@dataclass
class FetchMeta:
    team_name: str
    opponent_name: str
    team_id: str
    opponent_id: str
    title: str
    window_gte: str
    window_lte: str
    series_found: int
    series_analyzed: int


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_name(s: Optional[str]) -> str:
    return (s or "").strip()


def _score_name(query: str, candidate: str) -> float:
    q = query.lower()
    c = candidate.lower()
    try:
        from rapidfuzz.fuzz import partial_ratio  # type: ignore

        return float(partial_ratio(q, c)) / 100.0
    except Exception:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, q, c).ratio()


def resolve_title_id(client: GridGraphQLClient, title_name: str) -> str:
    _, data = query_across_endpoints(client, CENTRAL_DATA_URLS, TITLES_QUERY, None)
    titles = data.get("titles", []) or []
    if not titles:
        raise RuntimeError("No titles returned from GRID Central Data.")

    name_lc = title_name.lower()
    aliases = {
        "lol": ["league of legends", "lol"],
        "league of legends": ["league of legends", "lol"],
        "valorant": ["valorant"],
    }
    candidates = aliases.get(name_lc, [name_lc])

    best_id: Optional[str] = None
    best_score = -1.0
    for t in titles:
        tname = _safe_name(t.get("name"))
        if not tname:
            continue
        score = max(_score_name(alias, tname) for alias in candidates)
        if score > best_score:
            best_score = score
            best_id = t.get("id")

    if not best_id:
        raise RuntimeError(f"Could not resolve title id for '{title_name}'.")
    return best_id


def _fetch_teams(client: GridGraphQLClient, name_query: str) -> List[Dict[str, Any]]:
    try:
        _, data = query_across_endpoints(
            client, CENTRAL_DATA_URLS, TEAMS_QUERY_EXTENDED, {"q": name_query}
        )
    except Exception:
        _, data = query_across_endpoints(client, CENTRAL_DATA_URLS, TEAMS_QUERY_BASIC, {"q": name_query})

    edges = data.get("teams", {}).get("edges", []) or []
    return [e.get("node") or {} for e in edges]


def resolve_team_id(client: GridGraphQLClient, team_name: str) -> Tuple[str, str, List[Dict[str, Any]]]:
    candidates = _fetch_teams(client, team_name)
    if not candidates:
        raise RuntimeError(f"No team candidates returned for '{team_name}'.")

    best_id: Optional[str] = None
    best_name: Optional[str] = None
    best_score = -1.0
    for c in candidates:
        cname = _safe_name(c.get("name"))
        if not cname:
            continue
        score = _score_name(team_name, cname)
        if score > best_score:
            best_score = score
            best_id = c.get("id")
            best_name = cname

    if not best_id or not best_name:
        raise RuntimeError(f"Could not resolve team id for '{team_name}'.")
    return best_id, best_name, candidates


def list_tournaments(
    client: GridGraphQLClient,
    title_id: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    name_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    def fetch_page(vars_with_after: Dict[str, Any]) -> Dict[str, Any]:
        _, data = query_across_endpoints(client, CENTRAL_DATA_URLS, TOURNAMENTS_QUERY, vars_with_after)
        return data

    tournaments = list(
        paginate_connection(
            fetch_page,
            {"titleId": title_id},
            connection_path=["tournaments"],
            page_size=page_size,
        )
    )

    if name_filter:
        nf = name_filter.lower()
        tournaments = [t for t in tournaments if nf in _safe_name(t.get("name")).lower()]
    return tournaments


def list_all_series(
    client: GridGraphQLClient,
    tournament_ids: List[str],
    window_gte: str,
    window_lte: str,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> List[Dict[str, Any]]:
    if not tournament_ids:
        return []

    def fetch_page(vars_with_after: Dict[str, Any]) -> Dict[str, Any]:
        _, data = query_across_endpoints(client, CENTRAL_DATA_URLS, ALL_SERIES_QUERY, vars_with_after)
        return data

    series = list(
        paginate_connection(
            fetch_page,
            {"tournamentIds": tournament_ids, "gte": window_gte, "lte": window_lte},
            connection_path=["allSeries"],
            page_size=page_size,
        )
    )
    return series


def _series_has_team_ids(series_node: Dict[str, Any], team_id: str, opponent_id: str) -> bool:
    teams = series_node.get("teams") or []
    team_ids = {((t.get("baseInfo") or {}).get("id")) for t in teams}
    return team_id in team_ids and opponent_id in team_ids


def _series_has_team_names(series_node: Dict[str, Any], team_name: str, opponent_name: str) -> bool:
    teams = series_node.get("teams") or []
    names = [((t.get("baseInfo") or {}).get("name") or "").lower() for t in teams]
    return team_name.lower() in " ".join(names) and opponent_name.lower() in " ".join(names)


def _candidate_team_ids_from_series(series: List[Dict[str, Any]], team_name: str) -> List[str]:
    ids: List[str] = []
    for s in series:
        for t in s.get("teams") or []:
            base = t.get("baseInfo") or {}
            name = (base.get("name") or "").lower()
            if team_name.lower() in name and base.get("id"):
                ids.append(base.get("id"))
    return sorted(set(ids))


def fetch_series_state(
    client: GridGraphQLClient, series_id: str, debug: bool = False
) -> Dict[str, Any]:
    try:
        _, data = query_across_endpoints(
            client, SERIES_STATE_URLS, SERIES_STATE_QUERY_CHARACTER, {"id": series_id}
        )
        return data.get("seriesState") or {}
    except Exception as exc:
        if debug:
            print(f"[seriesState] character failed for {series_id}: {exc}")
        _, data = query_across_endpoints(
            client, SERIES_STATE_URLS, SERIES_STATE_QUERY_BASIC, {"id": series_id}
        )
        return data.get("seriesState") or {}


def fetch_series_for_matchup(
    api_key: str,
    title: str,
    team_name: str,
    opponent_name: str,
    window_days_back: int,
    tournament_name_filter: Optional[str] = None,
    team_id_override: Optional[str] = None,
    opponent_id_override: Optional[str] = None,
    debug: bool = False,
) -> Tuple[List[RawSeriesRecord], FetchMeta]:
    client = GridGraphQLClient(api_key)

    title_id = resolve_title_id(client, title)
    if debug:
        print(f"[titles] resolved '{title}' -> {title_id}")

    if team_id_override:
        team_id = team_id_override
        team_label = team_name
        team_candidates: List[Dict[str, Any]] = []
    else:
        try:
            team_id, team_label, team_candidates = resolve_team_id(client, team_name)
        except Exception as exc:
            team_id = ""
            team_label = team_name
            team_candidates = []
            if debug:
                print(f"[teams] team resolve failed for '{team_name}': {exc}")
    if opponent_id_override:
        opponent_id = opponent_id_override
        opponent_label = opponent_name
        opponent_candidates: List[Dict[str, Any]] = []
    else:
        try:
            opponent_id, opponent_label, opponent_candidates = resolve_team_id(client, opponent_name)
        except Exception as exc:
            opponent_id = ""
            opponent_label = opponent_name
            opponent_candidates = []
            if debug:
                print(f"[teams] opponent resolve failed for '{opponent_name}': {exc}")

    if debug:
        print(f"[teams] team='{team_label}' ({team_id}) candidates={len(team_candidates)}")
        print(f"[teams] opponent='{opponent_label}' ({opponent_id}) candidates={len(opponent_candidates)}")

    tournaments = list_tournaments(client, title_id, name_filter=tournament_name_filter)
    if not tournaments and tournament_name_filter:
        if debug:
            print(f"[tournaments] filter '{tournament_name_filter}' returned 0; retrying without filter")
        tournaments = list_tournaments(client, title_id, name_filter=None)
    if debug:
        print(f"[tournaments] count={len(tournaments)}")

    tournament_ids = [t.get("id") for t in tournaments if t.get("id")]

    now = _now_utc()
    window_lte = _iso_z(now)
    window_gte = _iso_z(now - timedelta(days=window_days_back))

    series = list_all_series(client, tournament_ids, window_gte, window_lte)
    if debug:
        print(f"[allSeries] fetched={len(series)}")

    matchup_series = [
        s for s in series if team_id and opponent_id and _series_has_team_ids(s, team_id, opponent_id)
    ]
    if not matchup_series:
        if debug and series:
            sample = series[:5]
            for s in sample:
                teams = [
                    ((t.get("baseInfo") or {}).get("id"), (t.get("baseInfo") or {}).get("name"))
                    for t in s.get("teams") or []
                ]
                print(f"[matchup] sample series {s.get('id')} teams={teams}")
        # Fallback: try to infer team IDs from series by name match in this window.
        team_ids = _candidate_team_ids_from_series(series, team_label)
        opponent_ids = _candidate_team_ids_from_series(series, opponent_label)
        if debug:
            print(
                f"[matchup] no series by ids; candidate ids by name team={team_ids} opponent={opponent_ids}"
            )
        if team_ids and opponent_ids:
            inferred_team_id = team_ids[0]
            inferred_opponent_id = opponent_ids[0]
            matchup_series = [
                s for s in series if _series_has_team_ids(s, inferred_team_id, inferred_opponent_id)
            ]
            if matchup_series:
                team_id = inferred_team_id
                opponent_id = inferred_opponent_id
                if debug:
                    print(
                        f"[matchup] inferred ids used team={team_id} opponent={opponent_id}"
                    )
    if debug:
        print(f"[matchup] series={len(matchup_series)}")

    records: List[RawSeriesRecord] = []
    for s in matchup_series:
        series_id = s.get("id")
        if not series_id:
            continue
        state = fetch_series_state(client, series_id, debug=debug)
        records.append(
            RawSeriesRecord(
                series_id=series_id,
                start_time=s.get("startTimeScheduled") or "",
                tournament=s.get("tournament") or {},
                teams=s.get("teams") or [],
                series_state=state,
            )
        )

    meta = FetchMeta(
        team_name=team_label,
        opponent_name=opponent_label,
        team_id=team_id,
        opponent_id=opponent_id,
        title=title,
        window_gte=window_gte,
        window_lte=window_lte,
        series_found=len(matchup_series),
        series_analyzed=len(records),
    )
    return records, meta


def raw_records_to_json(records: List[RawSeriesRecord]) -> List[Dict[str, Any]]:
    return [
        {
            "series_id": r.series_id,
            "start_time": r.start_time,
            "tournament": r.tournament,
            "teams": r.teams,
            "series_state": r.series_state,
        }
        for r in records
    ]


def raw_records_from_json(items: List[Dict[str, Any]]) -> List[RawSeriesRecord]:
    return [
        RawSeriesRecord(
            series_id=i.get("series_id") or "",
            start_time=i.get("start_time") or "",
            tournament=i.get("tournament") or {},
            teams=i.get("teams") or [],
            series_state=i.get("series_state") or {},
        )
        for i in items
    ]
