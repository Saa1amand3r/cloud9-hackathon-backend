from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scouting.grid_ingest import fetch_series_for_matchup
from scouting.normalize import normalize_records
from scouting.report import build_report

app = FastAPI(
    title="LoL Scouting Report API",
    description="Generate professional scouting reports for League of Legends teams",
    version="1.0.0",
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScoutingReportRequest(BaseModel):
    """Request body for generating a scouting report."""
    team: str = Field(..., description="Your team name (e.g., 'Cloud9')")
    opponent: str = Field(..., description="Opponent team name (e.g., 'Team Liquid')")
    window_days: int = Field(
        default=2000,
        ge=1,
        le=3650,
        description="Number of days back to analyze (default: 180)"
    )
    tournament_filter: Optional[str] = Field(
        default=None,
        description="Optional tournament name filter (e.g., 'LCS', 'Worlds')"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    api_key_configured: bool


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "LoL Scouting Report API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "generate_report": "/api/scouting/report (POST)",
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and configuration status."""
    api_key = os.environ.get("GRID_API_KEY")
    return {
        "status": "healthy",
        "api_key_configured": bool(api_key),
    }


@app.post("/api/scouting/report")
async def generate_scouting_report(request: ScoutingReportRequest):
    """
    Generate a comprehensive scouting report for an opponent team.

    This endpoint analyzes historical match data and returns detailed insights
    including player tendencies, draft patterns, win conditions, and strategic
    recommendations.

    **Required**: Set the `GRID_API_KEY` environment variable.
    """
    api_key = os.environ.get("GRID_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GRID_API_KEY not configured. Set it as an environment variable."
        )

    try:
        # Fetch data from GRID API
        records, meta = fetch_series_for_matchup(
            api_key=api_key,
            title="lol",
            team_name=request.team,
            opponent_name=request.opponent,
            window_days_back=request.window_days,
            tournament_name_filter=request.tournament_filter,
            debug=False,
        )

        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No matches found between '{request.team}' and '{request.opponent}' in the last {request.window_days} days."
            )

        if not meta:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve match metadata."
            )

        # Normalize records and build report
        games = normalize_records(records, meta.team_id, meta.opponent_id)

        if not games:
            raise HTTPException(
                status_code=404,
                detail="No game data available after normalization."
            )

        report = build_report(games, meta)

        return {
            "success": True,
            "request": {
                "team": request.team,
                "opponent": request.opponent,
                "window_days": request.window_days,
                "tournament_filter": request.tournament_filter,
            },
            "report": report,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )


@app.get("/api/scouting/report")
async def generate_scouting_report_get(
    team: str = Query(..., description="Your team name"),
    opponent: str = Query(..., description="Opponent team name"),
    window_days: int = Query(default=180, ge=1, le=3650, description="Days back to analyze"),
    tournament_filter: Optional[str] = Query(default=None, description="Tournament filter"),
):
    """
    Generate a scouting report via GET request.

    Same as POST but with query parameters for easier testing.
    """
    request = ScoutingReportRequest(
        team=team,
        opponent=opponent,
        window_days=window_days,
        tournament_filter=tournament_filter,
    )
    return await generate_scouting_report(request)
