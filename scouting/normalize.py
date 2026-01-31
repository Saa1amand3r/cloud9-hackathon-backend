from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .grid_ingest import RawSeriesRecord


@dataclass(frozen=True)
class TeamRef:
    id: str
    name: str


@dataclass
class PlayerPerf:
    player_id: str
    name: Optional[str]
    role: Optional[str]
    character: Optional[str]
    kills: int
    deaths: int


@dataclass
class TeamGameState:
    team_id: str
    won: Optional[bool]
    score: Optional[int]
    kills: int
    deaths: int
    players: List[PlayerPerf]


@dataclass
class GameRecord:
    series_id: str
    game_number: int
    start_time: str
    tournament: Dict[str, Any]
    team: TeamGameState
    opponent: TeamGameState
    result: str


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _get_character(player: Dict[str, Any]) -> Optional[str]:
    for key in ("character", "champion", "agent"):
        val = player.get(key)
        if val:
            if isinstance(val, dict):
                return val.get("name") or val.get("id")
            return str(val)
    return None


def _load_role_map() -> Dict[str, str]:
    # Allow override via env var; fall back to bundled role_map.json
    override = os.environ.get("SCOUTING_ROLE_MAP")
    if override:
        path = Path(override)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    default_path = Path(__file__).with_name("role_map.json")
    if default_path.exists():
        return json.loads(default_path.read_text(encoding="utf-8"))
    return {}


def _get_role(player: Dict[str, Any]) -> Optional[str]:
    for key in ("role", "lane", "position"):
        val = player.get(key)
        if val:
            return str(val)
    return None


def _normalize_players(players: List[Dict[str, Any]]) -> List[PlayerPerf]:
    out: List[PlayerPerf] = []
    role_map = _load_role_map()
    for p in players:
        character = _get_character(p)
        role = _get_role(p)
        if not role and character:
            role = role_map.get(character)
        out.append(
            PlayerPerf(
                player_id=str(p.get("id") or ""),
                name=p.get("name"),
                role=role,
                character=character,
                kills=_safe_int(p.get("kills")),
                deaths=_safe_int(p.get("deaths")),
            )
        )
    return out


def _team_state_from_entry(entry: Dict[str, Any]) -> TeamGameState:
    return TeamGameState(
        team_id=str(entry.get("id") or ""),
        won=entry.get("won") if entry.get("won") is not None else None,
        score=_safe_int(entry.get("score")) if entry.get("score") is not None else None,
        kills=_safe_int(entry.get("kills")),
        deaths=_safe_int(entry.get("deaths")),
        players=_normalize_players(entry.get("players") or []),
    )


def _result_from_states(team: TeamGameState, opponent: TeamGameState) -> str:
    if team.won is True:
        return "win"
    if opponent.won is True:
        return "loss"
    return "unknown"


def normalize_records(
    records: List[RawSeriesRecord],
    team_id: str,
    opponent_id: str,
) -> List[GameRecord]:
    games: List[GameRecord] = []

    for record in records:
        state = record.series_state or {}
        state_games = state.get("games") or []

        if state_games:
            for g in state_games:
                teams = g.get("teams") or []
                team_entry = next((t for t in teams if str(t.get("id")) == team_id), None)
                opp_entry = next((t for t in teams if str(t.get("id")) == opponent_id), None)
                if not team_entry or not opp_entry:
                    continue
                team_state = _team_state_from_entry(team_entry)
                opp_state = _team_state_from_entry(opp_entry)
                games.append(
                    GameRecord(
                        series_id=record.series_id,
                        game_number=_safe_int(g.get("sequenceNumber")) or 0,
                        start_time=record.start_time,
                        tournament=record.tournament,
                        team=team_state,
                        opponent=opp_state,
                        result=_result_from_states(team_state, opp_state),
                    )
                )
            continue

        # Fallback: no games array, use series_state.teams aggregates if available
        teams = state.get("teams") or []
        team_entry = next((t for t in teams if str(t.get("id")) == team_id), None)
        opp_entry = next((t for t in teams if str(t.get("id")) == opponent_id), None)
        if not team_entry or not opp_entry:
            continue
        team_state = _team_state_from_entry(team_entry)
        opp_state = _team_state_from_entry(opp_entry)
        games.append(
            GameRecord(
                series_id=record.series_id,
                game_number=0,
                start_time=record.start_time,
                tournament=record.tournament,
                team=team_state,
                opponent=opp_state,
                result=_result_from_states(team_state, opp_state),
            )
        )

    return games
