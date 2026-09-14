import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from db.supabase_client import get_supabase
from db.repository import TrafficWindowRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/traffic", tags=["traffic"])

def _record_to_dict(window: dict) -> dict:
    """Convert Supabase dict to API response format."""
    
    # Parse by_class from vehicle_distribution JSONB column
    by_class = window.get("vehicle_distribution", {})
    
    return {
        "window_start": window.get("start_time"),
        "window_end": window.get("end_time"),
        "unique_vehicle_count": window.get("vehicle_count"),
        "congestion_score": window.get("congestion_score"),
        "congestion_level": window.get("congestion_level"),
        "by_class": by_class,
        "video_id": window.get("video_id"),
        "gps_available": False,  # Window-level GPS aggregation not implemented yet
        "latitude": None,
        "longitude": None,
        "created_at": window.get("created_at")
    }

@router.get("/current")
async def get_current_traffic():
    """
    Get the most recently recorded traffic window across the system.
    """
    client = get_supabase()
    repo = TrafficWindowRepository(client)
    record = repo.get_latest()

    if not record:
        return {
            "available": False,
            "message": "No traffic data has been processed yet."
        }

    resp = _record_to_dict(record)
    resp["available"] = True
    resp["note"] = "Data is from latest processed window."
    return resp

@router.get("/history")
async def get_traffic_history(
    video_id: Optional[str] = Query(None, description="Filter by specific video"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get historical traffic windows, ordered by most recent first.
    """
    client = get_supabase()
    repo = TrafficWindowRepository(client)
    records = repo.get_history(video_id=video_id, limit=limit)
    
    return {
        "windows": [_record_to_dict(r) for r in records],
        "total": len(records),
        "note": "Windows are ordered most-recent first."
    }
