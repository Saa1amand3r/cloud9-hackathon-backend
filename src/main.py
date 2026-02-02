"""Main FastAPI application with hexagonal architecture."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .api.rest.routes import router as analysis_router
from .api.websocket.handlers import handle_report_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Cloudy Poro API",
    description="Professional esports scouting and analysis API for League of Legends",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "https://cloudyporo.com",  # Production
        "*",  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    api_key_configured: bool


@app.get("/", tags=["meta"])
async def root():
    """API root with information and available endpoints."""
    return {
        "name": "Cloudy Poro API",
        "version": "2.0.0",
        "description": "Professional esports scouting API",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /health",
            "analysis": "GET /api/teams/{team_id}/analysis",
            "generate": "POST /api/analysis/generate",
            "websocket": "WS /ws/report",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check():
    """Check API health and configuration status."""
    api_key = os.environ.get("GRID_API_KEY")
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        api_key_configured=bool(api_key),
    )


# Include REST routes
app.include_router(analysis_router)


# WebSocket endpoint for report generation with progress
@app.websocket("/ws/report")
async def websocket_report(websocket: WebSocket):
    """WebSocket endpoint for real-time report generation.

    Connect to this endpoint and send:
    {
        "action": "generate",
        "teamName": "T1",
        "opponentName": "Gen.G",  // Optional, defaults to teamName
        "ourTeam": "Cloud9",       // Optional, defaults to "Cloud9"
        "windowDays": 180,         // Optional
        "tournamentFilter": "LCK"  // Optional
    }

    You will receive progress updates:
    {
        "status": "connecting" | "processing" | "completed" | "error",
        "progress": 0-100,
        "message": "Status message"
    }

    On completion, the final message includes the full report:
    {
        "status": "completed",
        "progress": 100,
        "message": "Report ready!",
        "report": { ... full TeamAnalysisReport ... }
    }
    """
    await handle_report_websocket(websocket)


# Add a convenience endpoint for fetching report after WebSocket completion
@app.get("/api/reports/{team_id}", tags=["analysis"])
async def get_cached_report(team_id: str):
    """Get a cached report if available.

    Note: Reports are generated via WebSocket or POST /api/analysis/generate.
    This endpoint is for fetching previously generated reports.
    Currently returns 404 as caching is not implemented.
    """
    return {
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": "Report caching not yet implemented. Use WebSocket or POST /api/analysis/generate.",
            "details": {"teamId": team_id},
        }
    }
