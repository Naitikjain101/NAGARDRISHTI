"""
Urban Watch — Mission & Map Intelligence API

All endpoints the frontend / map will consume.

Endpoints:
  GET  /api/missions/                        — list all registered missions
  POST /api/missions/register               — ingest a mission JSON
  POST /api/missions/{id}/start             — create/resume session, start telemetry
  POST /api/missions/{id}/seek              — seek to timestamp (replay mode)
  GET  /api/missions/{id}/telemetry         — live telemetry snapshot (polling)
  GET  /api/missions/{id}/incidents         — all incidents for this mission
  GET  /api/missions/{id}/route             — GPS route points (for map polyline)
  GET  /api/incidents/{id}/evidence         — jump-to-frame data for map click
  GET  /api/map/incidents                   — all incidents across all missions (map overlay)
  GET  /api/map/buses                       — current live bus positions
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import JSONResponse

from db.supabase_client import get_supabase
from db.mission_repository import MissionRepository
from missions.ingestion import MissionIngester, MissionIngestionError
from missions import session as session_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["missions"])

DEMO_VIDEOS_DIR = Path("demo_videos")
DEMO_MISSIONS_DIR = Path("demo_missions")


# ── Helper ─────────────────────────────────────────────────────────────────────

def _mission_not_found(mission_id: str):
    raise HTTPException(status_code=404, detail=f"Mission not found: {mission_id}")


# ──────────────────────────────────────────────────────────────────────────────
# MISSION MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/missions/")
async def list_missions():
    """
    List all registered demo missions.
    Returns id, bus_id, route_name, video_filename, duration, status.
    """
    client = get_supabase()
    repo   = MissionRepository(client)
    missions = repo.get_all_missions()
    return {"missions": missions, "count": len(missions)}


@router.post("/api/missions/register")
async def register_mission(payload: Dict[str, Any] = Body(...)):
    """
    Register a demo mission from a metadata JSON payload.

    Body: MissionMetadata JSON (bus_id, route_id, route_name, video_filename,
          duration, gps: [{timestamp, lat, lng}, ...])

    Idempotent: re-registering the same bus+video returns the existing mission.
    """
    client = get_supabase()
    ingester = MissionIngester(client, demo_dir=DEMO_VIDEOS_DIR)
    try:
        record = ingester.ingest(payload)
    except MissionIngestionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "mission_id":   record.id,
        "bus_id":       record.bus_id,
        "route_name":   record.route_name,
        "status":       record.status,
        "message":      "Mission registered successfully",
    }


@router.post("/api/missions/{mission_id}/start")
async def start_mission(mission_id: str, mode: str = Query(default="replay")):
    """
    Start or resume a mission session.
    Creates an in-memory MissionSession for telemetry.

    mode: "replay" (video-driven) | "live" (camera-driven)
    """
    client = get_supabase()
    repo   = MissionRepository(client)

    mission = repo.get_mission(mission_id)
    if not mission:
        _mission_not_found(mission_id)

    route_points = repo.get_route_points(mission_id)
    if len(route_points) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Mission {mission_id} has insufficient GPS route points"
        )

    sess = session_manager.create_or_resume_session(
        mission_id=mission_id,
        bus_id=mission["bus_id"],
        route_name=mission["route_name"],
        mode=mode,
        route_points=route_points,
    )

    repo.update_mission_status(mission_id, "RUNNING")

    snap = sess.snapshot()
    return {
        "mission_id":  mission_id,
        "bus_id":      snap.bus_id,
        "route_name":  snap.route_name,
        "mode":        snap.mode,
        "start_lat":   snap.current_lat,
        "start_lng":   snap.current_lng,
        "message":     f"Mission {mode} session started",
    }


@router.post("/api/missions/{mission_id}/seek")
async def seek_mission(
    mission_id: str,
    timestamp: float = Body(..., embed=True, description="Seconds into video")
):
    """
    Seek the mission replay to a specific video timestamp.
    The telemetry bus position will update immediately.
    """
    sess = session_manager.get_session(mission_id)
    if not sess:
        raise HTTPException(
            status_code=404,
            detail=f"No active session for mission {mission_id}. Call /start first."
        )
    sess.seek(timestamp)
    snap = sess.snapshot()
    return {
        "mission_id":        mission_id,
        "current_timestamp": snap.current_timestamp,
        "current_lat":       snap.current_lat,
        "current_lng":       snap.current_lng,
    }


# ──────────────────────────────────────────────────────────────────────────────
# TELEMETRY (live polling by frontend)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/missions/{mission_id}/telemetry")
async def get_telemetry(mission_id: str):
    """
    Live telemetry snapshot for a running mission.
    Frontend polls this every 1-2 seconds to update bus position and counts.

    Returns TelemetrySnapshot JSON.
    """
    sess = session_manager.get_session(mission_id)
    if not sess:
        # Return a static snapshot from DB if no live session
        client = get_supabase()
        repo   = MissionRepository(client)
        mission = repo.get_mission(mission_id)
        if not mission:
            _mission_not_found(mission_id)
        route_points = repo.get_route_points(mission_id)
        if route_points:
            first = route_points[0]
            return {
                "mission_id":        mission_id,
                "bus_id":            mission["bus_id"],
                "route_name":        mission["route_name"],
                "mode":              "replay",
                "current_timestamp": 0.0,
                "current_lat":       first["lat"],
                "current_lng":       first["lng"],
                "ai_status":         "idle",
                "pothole_count":     0,
                "waterlogging_count": 0,
                "vehicle_count":     0,
            }
        _mission_not_found(mission_id)

    return sess.snapshot().model_dump()


# ──────────────────────────────────────────────────────────────────────────────
# MISSION DATA
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/missions/{mission_id}/incidents")
async def get_mission_incidents(mission_id: str):
    """
    All incidents sourced from this mission, with observation count.
    Used by the frontend to populate the mission-specific incident list.
    """
    client = get_supabase()

    # Check mission exists
    repo = MissionRepository(client)
    if not repo.get_mission(mission_id):
        _mission_not_found(mission_id)

    # Get all incidents where source_mission_id = this mission
    # OR any incident with an observation from this mission
    obs_resp = client.table("incident_observations") \
        .select("incident_id") \
        .eq("mission_id", mission_id) \
        .execute()

    incident_ids = list({r["incident_id"] for r in (obs_resp.data or [])})
    if not incident_ids:
        return {"incidents": [], "total": 0, "mission_id": mission_id}

    inc_resp = client.table("incidents") \
        .select("*") \
        .in_("id", incident_ids) \
        .order("first_seen_at", desc=False) \
        .execute()

    incidents = inc_resp.data or []
    return {
        "incidents": incidents,
        "total":     len(incidents),
        "mission_id": mission_id,
    }


@router.get("/api/missions/{mission_id}/route")
async def get_mission_route(mission_id: str):
    """
    GPS route points for a mission (used to draw the bus polyline on the map).
    Returns [{timestamp, lat, lng}, ...] in timestamp order.
    """
    client = get_supabase()
    repo   = MissionRepository(client)

    if not repo.get_mission(mission_id):
        _mission_not_found(mission_id)

    points = repo.get_route_points(mission_id)
    return {"mission_id": mission_id, "route_points": points, "count": len(points)}


# ──────────────────────────────────────────────────────────────────────────────
# EVIDENCE TRACEABILITY (click incident → jump to frame)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/incidents/{incident_id}/evidence")
async def get_incident_evidence(incident_id: str):
    """
    Traceability endpoint: given an incident ID (from map click),
    returns all observations including video_timestamp.

    The frontend uses video_timestamp to seek the video player to the exact frame.

    Response:
      incident_id, incident_type, latitude, longitude,
      observations: [{mission_id, bus_id, video_timestamp, confidence, bbox, ...}]
    """
    client = get_supabase()

    # Fetch incident
    inc_resp = client.table("incidents") \
        .select("*").eq("id", incident_id).execute()
    if not inc_resp.data:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    incident = inc_resp.data[0]

    # Fetch all observations
    repo = MissionRepository(client)
    observations = repo.get_observations_for_incident(incident_id)

    # Enrich with mission info
    enriched_obs = []
    for obs in observations:
        mission_id = obs.get("mission_id")
        mission_info = {}
        if mission_id:
            m = repo.get_mission(mission_id)
            if m:
                mission_info = {
                    "bus_id":         m["bus_id"],
                    "route_name":     m["route_name"],
                    "video_filename": m["video_filename"],
                }
        enriched_obs.append({**obs, **mission_info})

    return {
        "incident_id":       incident_id,
        "incident_type":     incident.get("incident_type"),
        "severity":          incident.get("severity"),
        "latitude":          incident.get("latitude"),
        "longitude":         incident.get("longitude"),
        "observation_count": incident.get("observation_count", 1),
        "observed_by":       incident.get("observed_by", []),
        "dedup_status":      incident.get("dedup_status", "PENDING"),
        "observations":      enriched_obs,
    }


# ──────────────────────────────────────────────────────────────────────────────
# MAP OVERLAY FEEDS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/map/incidents")
async def get_map_incidents(
    incident_type: Optional[str] = Query(default=None),
    min_confidence: float        = Query(default=0.0, ge=0.0, le=1.0),
    dedup_status: Optional[str]  = Query(default=None, description="PENDING|CONFIRMED"),
    limit: int                   = Query(default=500, ge=1, le=2000),
):
    """
    All geo-referenced incidents for the map overlay.

    Designed to be fast: returns only the fields the map needs.
    The full evidence trail is fetched lazily on incident click via /evidence.
    """
    client = get_supabase()

    q = client.table("incidents") \
        .select("id, incident_type, severity, status, confidence, latitude, longitude, "
                "observation_count, observed_by, dedup_status, first_seen_at, last_seen_at") \
        .not_.is_("latitude", "null") \
        .not_.is_("longitude", "null") \
        .gte("confidence", min_confidence)

    if incident_type:
        q = q.eq("incident_type", incident_type)
    if dedup_status:
        q = q.eq("dedup_status", dedup_status)

    resp = q.order("last_seen_at", desc=True).limit(limit).execute()

    return {
        "incidents": resp.data or [],
        "total":     len(resp.data or []),
        "filters": {
            "incident_type":  incident_type,
            "min_confidence": min_confidence,
            "dedup_status":   dedup_status,
        }
    }


@router.get("/api/map/buses")
async def get_map_buses():
    """
    Current live position of all active bus sessions.
    Used to animate bus markers on the map.

    Returns one entry per active MissionSession.
    """
    snapshots = session_manager.list_active_sessions()
    buses = [
        {
            "mission_id":        s.mission_id,
            "bus_id":            s.bus_id,
            "route_name":        s.route_name,
            "current_lat":       s.current_lat,
            "current_lng":       s.current_lng,
            "speed_kmh":         s.speed_kmh,
            "ai_status":         s.ai_status,
            "pothole_count":     s.pothole_count,
            "waterlogging_count": s.waterlogging_count,
        }
        for s in snapshots
        if s.current_lat is not None
    ]
    return {"buses": buses, "count": len(buses)}
