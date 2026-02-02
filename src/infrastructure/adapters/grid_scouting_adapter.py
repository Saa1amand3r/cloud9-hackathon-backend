"""Adapter wrapping the GRID scouting module."""

from typing import Any, Dict, List, Tuple
import os

from scouting.grid_ingest import fetch_series_for_matchup, RawSeriesRecord, FetchMeta
from scouting.normalize import normalize_records, GameRecord
from scouting.report import build_report

from ...application.ports.scouting_service import (
    FetchMetadata,
    RawGameData,
    ScoutingDataPort,
)
from ...application.ports.report_builder import ReportBuilderPort


class GridScoutingAdapter(ScoutingDataPort):
    """Adapter for fetching scouting data from GRID API."""

    def __init__(self, api_key: str | None = None):
        """Initialize with API key.

        Args:
            api_key: GRID API key. If None, will try to get from environment.
        """
        self._api_key = api_key or os.environ.get("GRID_API_KEY", "")

    def fetch_matchup_data(
        self,
        team_name: str,
        opponent_name: str,
        window_days: int,
        tournament_filter: str | None = None,
    ) -> Tuple[List[RawGameData], FetchMetadata | None]:
        """Fetch matchup data between two teams from GRID API.

        Args:
            team_name: Our team name
            opponent_name: Opponent team name
            window_days: Days to look back
            tournament_filter: Optional tournament name filter

        Returns:
            Tuple of (raw game data list, fetch metadata)
        """
        if not self._api_key:
            raise ValueError("GRID_API_KEY not configured")

        # Fetch raw series from GRID
        records, meta = fetch_series_for_matchup(
            api_key=self._api_key,
            title="lol",
            team_name=team_name,
            opponent_name=opponent_name,
            window_days_back=window_days,
            tournament_name_filter=tournament_filter,
            debug=False,
        )

        if not records or not meta:
            return [], None

        # Store the raw records and meta for later use by report builder
        self._last_records = records
        self._last_meta = meta

        # Convert to domain format
        fetch_metadata = FetchMetadata(
            team_name=meta.team_name,
            opponent_name=meta.opponent_name,
            team_id=meta.team_id,
            opponent_id=meta.opponent_id,
            title=meta.title,
            window_start=meta.window_gte,
            window_end=meta.window_lte,
            series_found=meta.series_found,
            series_analyzed=meta.series_analyzed,
        )

        # Normalize records to get game data
        games = normalize_records(records, meta.team_id, meta.opponent_id)

        raw_games = [
            RawGameData(
                series_id=g.series_id,
                game_number=g.game_number,
                start_time=g.start_time,
                tournament=g.tournament,
                team_data={
                    "team_id": g.team.team_id,
                    "won": g.team.won,
                    "score": g.team.score,
                    "kills": g.team.kills,
                    "deaths": g.team.deaths,
                    "players": [
                        {
                            "player_id": p.player_id,
                            "name": p.name,
                            "role": p.role,
                            "character": p.character,
                            "kills": p.kills,
                            "deaths": p.deaths,
                        }
                        for p in g.team.players
                    ],
                },
                opponent_data={
                    "team_id": g.opponent.team_id,
                    "won": g.opponent.won,
                    "score": g.opponent.score,
                    "kills": g.opponent.kills,
                    "deaths": g.opponent.deaths,
                    "players": [
                        {
                            "player_id": p.player_id,
                            "name": p.name,
                            "role": p.role,
                            "character": p.character,
                            "kills": p.kills,
                            "deaths": p.deaths,
                        }
                        for p in g.opponent.players
                    ],
                },
                result=g.result,
            )
            for g in games
        ]

        return raw_games, fetch_metadata


class GridReportBuilderAdapter(ReportBuilderPort):
    """Adapter for building reports using the scouting module."""

    def __init__(self, scouting_adapter: GridScoutingAdapter):
        """Initialize with scouting adapter reference.

        Args:
            scouting_adapter: The scouting adapter that fetched the data
        """
        self._scouting_adapter = scouting_adapter

    def build_raw_report(
        self,
        games: List[RawGameData],
        meta: FetchMetadata,
    ) -> Dict[str, Any]:
        """Build a raw analysis report from game data.

        Args:
            games: List of raw game data
            meta: Fetch metadata

        Returns:
            Raw report dictionary in internal format
        """
        # Use the stored records and meta from the scouting adapter
        records = getattr(self._scouting_adapter, "_last_records", [])
        scouting_meta = getattr(self._scouting_adapter, "_last_meta", None)

        if not records or not scouting_meta:
            raise ValueError("No data available for building report")

        # Normalize and build report using existing scouting module
        normalized_games = normalize_records(
            records, scouting_meta.team_id, scouting_meta.opponent_id
        )

        if not normalized_games:
            raise ValueError("No game data available after normalization")

        return build_report(normalized_games, scouting_meta)
