"""WebSocket handlers for real-time report generation progress."""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

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


class WebSocketProgressCallback(ProgressCallbackPort):
    """Progress callback that sends updates via WebSocket."""

    def __init__(self, websocket: WebSocket):
        self._websocket = websocket

    async def report_progress(
        self, progress: int, message: str, status: str = "processing"
    ) -> None:
        """Send progress update via WebSocket."""
        await self._websocket.send_json({
            "status": status,
            "progress": progress,
            "message": message,
        })


async def handle_report_websocket(websocket: WebSocket) -> None:
    """Handle WebSocket connection for report generation.

    Expected client message format:
    {
        "action": "generate",
        "teamName": "T1"
    }

    Server sends progress updates:
    {
        "status": "connecting" | "processing" | "completed" | "error",
        "progress": 0-100,
        "message": "Human-readable status"
    }

    Args:
        websocket: FastAPI WebSocket connection
    """
    await websocket.accept()

    try:
        # Wait for initial message with team name
        data = await websocket.receive_json()

        action = data.get("action")
        if action != "generate":
            await websocket.send_json({
                "status": "error",
                "progress": 0,
                "message": f"Unknown action: {action}",
            })
            await websocket.close()
            return

        team_name = data.get("teamName")
        opponent_name = data.get("opponentName", team_name)  # Default to same for all-opponent analysis
        our_team = data.get("ourTeam", "Cloud9")
        window_days = data.get("windowDays", 180)
        tournament_filter = data.get("tournamentFilter")

        if not team_name:
            await websocket.send_json({
                "status": "error",
                "progress": 0,
                "message": "teamName is required",
            })
            await websocket.close()
            return

        # Send initial connecting status
        await websocket.send_json({
            "status": "connecting",
            "progress": 0,
            "message": "Initializing...",
        })

        # Create progress callback
        progress_callback = WebSocketProgressCallback(websocket)

        # Create adapters
        scouting_adapter = GridScoutingAdapter()
        report_builder = GridReportBuilderAdapter(scouting_adapter)

        # Execute use case with progress tracking
        use_case = GenerateReportUseCase(scouting_adapter, report_builder)
        request = GenerateReportRequest(
            team_name=our_team,
            opponent_name=opponent_name if opponent_name != team_name else team_name,
            window_days=window_days,
            tournament_filter=tournament_filter,
        )

        result = await use_case.execute(request, progress_callback)

        if not result.success:
            await websocket.send_json({
                "status": "error",
                "progress": 0,
                "message": result.error or "Failed to generate report",
            })
            await websocket.close()
            return

        # Transform to frontend format
        try:
            # Debug: Log report structure
            logger.info(f"Report keys: {list(result.report.keys()) if result.report else 'None'}")
            if result.report and "per_player" in result.report:
                logger.info(f"per_player type: {type(result.report['per_player'])}")
                if isinstance(result.report["per_player"], dict):
                    for pid, pdata in list(result.report["per_player"].items())[:1]:
                        logger.info(f"Sample player {pid}: comfort_picks type = {type(pdata.get('comfort_picks'))}")
                        if "comfort_picks" in pdata:
                            picks = pdata["comfort_picks"]
                            if picks:
                                logger.info(f"First comfort pick type: {type(picks[0])}, value: {picks[0]}")

            frontend_report = transform_report_to_frontend(
                result.report,
                result.metadata or {},
            )
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Transform error: {error_details}")
            await websocket.send_json({
                "status": "error",
                "progress": 0,
                "message": f"Transform error: {str(e)}",
            })
            await websocket.close()
            return

        # Send completion with report data
        await websocket.send_json({
            "status": "completed",
            "progress": 100,
            "message": "Report ready!",
            "report": frontend_report,
        })

        # Keep connection alive briefly for client to receive
        await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass  # Client disconnected
    except json.JSONDecodeError:
        await websocket.send_json({
            "status": "error",
            "progress": 0,
            "message": "Invalid JSON message",
        })
    except Exception as e:
        try:
            await websocket.send_json({
                "status": "error",
                "progress": 0,
                "message": f"Error: {str(e)}",
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
