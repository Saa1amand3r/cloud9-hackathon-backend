"""REST API routes for team analysis."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..transformers.report_transformer import transform_report_to_frontend
from ...application.ports.scouting_service import ProgressCallbackPort
from ...application.use_cases.generate_report import (
    GenerateReportRequest,
    GenerateReportUseCase,
)
from ...infrastructure.adapters.grid_scouting_adapter import (
    GridReportBuilderAdapter,
    GridScoutingAdapter,
)

router = APIRouter(prefix="/api", tags=["analysis"])


class AnalysisRequest(BaseModel):
    """Request body for team analysis."""

    team_name: str = Field(
        ...,
        alias="teamName",
        description="Your team name",
        min_length=1,
    )
    opponent_name: str = Field(
        ...,
        alias="opponentName",
        description="Opponent team name to analyze",
        min_length=1,
    )
    window_days: int = Field(
        default=2000,
        alias="windowDays",
        ge=1,
        le=3650,
        description="Days back to analyze",
    )
    tournament_filter: Optional[str] = Field(
        default=None,
        alias="tournamentFilter",
        description="Optional tournament filter",
    )

    class Config:
        populate_by_name = True


class ErrorResponse(BaseModel):
    """Error response model."""

    code: str
    message: str
    details: dict = {}


@router.get("/teams/{team_id}/analysis")
async def get_team_analysis(
    team_id: str,
    start_date: Optional[str] = Query(None, alias="startDate"),
    end_date: Optional[str] = Query(None, alias="endDate"),
    patch_version: Optional[str] = Query(None, alias="patchVersion"),
    last_n_games: Optional[int] = Query(None, alias="lastNGames"),
    include_player_analysis: bool = Query(True, alias="includePlayerAnalysis"),
    our_team: str = Query("Cloud9", alias="ourTeam", description="Your team name"),
):
    """Get team analysis report.

    This endpoint returns a comprehensive analysis of the specified team
    in the format expected by the frontend.

    Args:
        team_id: Team identifier or name to analyze
        start_date: Analysis start date (ISO 8601)
        end_date: Analysis end date (ISO 8601)
        patch_version: Game patch version filter
        last_n_games: Analyze only last N games
        include_player_analysis: Include per-player analysis
        our_team: Your team name for matchup context

    Returns:
        TeamAnalysisReport in frontend format
    """
    # Calculate window_days from dates if provided
    window_days = 2000
    if last_n_games:
        # Approximate: assume ~3 games per week
        window_days = max(30, last_n_games * 7 // 3)

    try:
        # Create adapters
        scouting_adapter = GridScoutingAdapter()
        report_builder = GridReportBuilderAdapter(scouting_adapter)

        # Execute use case
        use_case = GenerateReportUseCase(scouting_adapter, report_builder)
        request = GenerateReportRequest(
            team_name=our_team,
            opponent_name=team_id,
            window_days=window_days,
        )

        result = await use_case.execute(request)

        if not result.success:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "TEAM_NOT_FOUND",
                        "message": result.error or "Team not found or no data available",
                        "details": {"teamId": team_id},
                    }
                },
            )

        # Transform to frontend format
        frontend_report = transform_report_to_frontend(
            result.report,
            result.metadata or {},
        )

        return frontend_report

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(e),
                    "details": {},
                }
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Error generating report: {str(e)}",
                    "details": {},
                }
            },
        )


@router.post("/analysis/generate")
async def generate_analysis(request: AnalysisRequest):
    """Generate a new team analysis report.

    This endpoint generates a fresh analysis report for the specified matchup.

    Args:
        request: Analysis request with team names and options

    Returns:
        TeamAnalysisReport in frontend format
    """
    try:
        # Create adapters
        scouting_adapter = GridScoutingAdapter()
        report_builder = GridReportBuilderAdapter(scouting_adapter)

        # Execute use case
        use_case = GenerateReportUseCase(scouting_adapter, report_builder)
        gen_request = GenerateReportRequest(
            team_name=request.team_name,
            opponent_name=request.opponent_name,
            window_days=request.window_days,
            tournament_filter=request.tournament_filter,
        )

        result = await use_case.execute(gen_request)

        if not result.success:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "NO_DATA",
                        "message": result.error or "No data available for analysis",
                        "details": {
                            "team": request.team_name,
                            "opponent": request.opponent_name,
                        },
                    }
                },
            )

        # Transform to frontend format
        frontend_report = transform_report_to_frontend(
            result.report,
            result.metadata or {},
        )

        return frontend_report

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(e),
                    "details": {},
                }
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Error generating report: {str(e)}",
                    "details": {},
                }
            },
        )
