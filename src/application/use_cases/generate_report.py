"""Use case for generating team analysis reports."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict

from ..ports.scouting_service import ProgressCallbackPort, ScoutingDataPort
from ..ports.report_builder import ReportBuilderPort

# Thread pool for running blocking I/O operations
_executor = ThreadPoolExecutor(max_workers=4)


@dataclass
class GenerateReportRequest:
    """Request to generate a report."""

    team_name: str
    opponent_name: str
    window_days: int = 2000
    tournament_filter: str | None = None


@dataclass
class GenerateReportResult:
    """Result of report generation."""

    success: bool
    report: Dict[str, Any] | None = None
    error: str | None = None
    metadata: Dict[str, Any] | None = None


class GenerateReportUseCase:
    """Use case for generating team analysis reports.

    This orchestrates the process of:
    1. Fetching data from external sources
    2. Processing and normalizing the data
    3. Building the analysis report
    """

    def __init__(
        self,
        scouting_service: ScoutingDataPort,
        report_builder: ReportBuilderPort,
    ):
        self._scouting_service = scouting_service
        self._report_builder = report_builder

    async def execute(
        self,
        request: GenerateReportRequest,
        progress_callback: ProgressCallbackPort | None = None,
    ) -> GenerateReportResult:
        """Execute the report generation use case.

        Args:
            request: Report generation request
            progress_callback: Optional callback for progress updates

        Returns:
            Report generation result
        """
        loop = asyncio.get_event_loop()

        try:
            # Step 1: Fetch data (run in thread to not block event loop)
            if progress_callback:
                await progress_callback.report_progress(
                    10, "Connecting to data sources...", "processing"
                )

            # Run blocking I/O in thread pool
            fetch_func = partial(
                self._scouting_service.fetch_matchup_data,
                team_name=request.team_name,
                opponent_name=request.opponent_name,
                window_days=request.window_days,
                tournament_filter=request.tournament_filter,
            )
            games, meta = await loop.run_in_executor(_executor, fetch_func)

            if not games:
                return GenerateReportResult(
                    success=False,
                    error=f"No matches found between '{request.team_name}' and '{request.opponent_name}' in the last {request.window_days} days.",
                )

            if not meta:
                return GenerateReportResult(
                    success=False,
                    error="Failed to retrieve match metadata.",
                )

            if progress_callback:
                await progress_callback.report_progress(
                    25, f"Found {len(games)} games to analyze...", "processing"
                )

            # Step 2: Build report (run in thread to not block event loop)
            if progress_callback:
                await progress_callback.report_progress(
                    45, "Analyzing draft patterns...", "processing"
                )

            build_func = partial(
                self._report_builder.build_raw_report,
                games,
                meta,
            )
            report = await loop.run_in_executor(_executor, build_func)

            if progress_callback:
                await progress_callback.report_progress(
                    65, "Processing player statistics...", "processing"
                )

            if not report:
                return GenerateReportResult(
                    success=False,
                    error="Failed to build analysis report.",
                )

            if progress_callback:
                await progress_callback.report_progress(
                    80, "Generating insights...", "processing"
                )

            # Step 3: Prepare metadata
            metadata = {
                "team": request.team_name,
                "opponent": request.opponent_name,
                "window_days": request.window_days,
                "tournament_filter": request.tournament_filter,
                "games_analyzed": len(games),
            }

            if progress_callback:
                await progress_callback.report_progress(
                    90, "Finalizing report...", "processing"
                )

            return GenerateReportResult(
                success=True,
                report=report,
                metadata=metadata,
            )

        except Exception as e:
            if progress_callback:
                await progress_callback.report_progress(
                    0, f"Error: {str(e)}", "error"
                )
            return GenerateReportResult(
                success=False,
                error=str(e),
            )
