"""Port (interface) for scouting data service."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Any, Dict


@dataclass
class FetchMetadata:
    """Metadata about fetched series data."""

    team_name: str
    opponent_name: str
    team_id: str
    opponent_id: str
    title: str
    window_start: str  # ISO 8601
    window_end: str  # ISO 8601
    series_found: int
    series_analyzed: int


@dataclass
class RawGameData:
    """Raw game data from external source."""

    series_id: str
    game_number: int
    start_time: str
    tournament: Dict[str, Any]
    team_data: Dict[str, Any]
    opponent_data: Dict[str, Any]
    result: str  # "win", "loss", "unknown"


class ScoutingDataPort(ABC):
    """Port for fetching scouting data from external sources."""

    @abstractmethod
    def fetch_matchup_data(
        self,
        team_name: str,
        opponent_name: str,
        window_days: int,
        tournament_filter: str | None = None,
    ) -> Tuple[List[RawGameData], FetchMetadata | None]:
        """Fetch matchup data between two teams.

        Args:
            team_name: Our team name
            opponent_name: Opponent team name
            window_days: Days to look back
            tournament_filter: Optional tournament name filter

        Returns:
            Tuple of (raw game data list, fetch metadata)
        """
        ...


class ProgressCallbackPort(ABC):
    """Port for reporting progress during long operations."""

    @abstractmethod
    async def report_progress(
        self, progress: int, message: str, status: str = "processing"
    ) -> None:
        """Report progress update.

        Args:
            progress: Progress percentage (0-100)
            message: Human-readable status message
            status: Status type (connecting, processing, completed, error)
        """
        ...
