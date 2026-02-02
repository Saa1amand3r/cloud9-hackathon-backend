"""Port (interface) for building analysis reports."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .scouting_service import FetchMetadata, RawGameData


class ReportBuilderPort(ABC):
    """Port for building analysis reports from raw data."""

    @abstractmethod
    def build_raw_report(
        self,
        games: List[RawGameData],
        meta: FetchMetadata,
    ) -> Dict[str, Any]:
        """Build a raw analysis report from game data.

        This returns the internal report format from the scouting module.

        Args:
            games: List of normalized game records
            meta: Fetch metadata

        Returns:
            Raw report dictionary in internal format
        """
        ...
