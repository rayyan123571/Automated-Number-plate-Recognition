# =============================================================================
# app/routes/tracking.py — Live vehicle tracking + auto-challan endpoints
# =============================================================================

import logging

from fastapi import APIRouter

from app.services.vehicle_tracker import tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.get(
    "/active",
    summary="List currently tracked vehicles",
    description="Returns all vehicle tracks currently held in memory.",
)
async def list_active_tracks() -> dict:
    tracks = tracker.active_tracks()
    return {
        "success": True,
        "count": len(tracks),
        "tracks": tracks,
    }


@router.post(
    "/reset",
    summary="Reset the in-memory tracker",
    description="Clears all tracking state. Useful between demo sessions.",
)
async def reset_tracks() -> dict:
    tracker.reset()
    return {"success": True, "message": "Tracker state cleared."}
