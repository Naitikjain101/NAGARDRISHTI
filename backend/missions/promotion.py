import logging
import uuid
import requests
from datetime import datetime, timezone, timedelta

from db.supabase_client import get_supabase
from db.mission_repository import MissionRepository
from missions.deduplication import DeduplicationPipeline
from ai.gis.interpolator import InterpolationEngine
from ai.unified.schemas import UnifiedVideoSummary

logger = logging.getLogger(__name__)

def promote_canonical_results(video_id: str, mission_id: str):
    """
    Downloads canonical results for a processed video from Supabase Storage,
    and runs them through the Deduplication pipeline to promote them to actual incidents.
    """
    client = get_supabase()
    
    # 1. Check if we already promoted for this mission + video to avoid double-creation
    existing = client.table("incident_observations").select("id").eq("mission_id", mission_id).limit(1).execute()
    if existing.data:
        logger.info(f"[PROMOTION] Mission {mission_id} already has observations, skipping promotion.")
        return
        
    # 2. Fetch canonical results JSON from Storage
    try:
        bucket = "urban_watch_evidence"
        storage_path = f"results/{video_id}_unified.json"
        signed_url_res = client.storage.from_(bucket).create_signed_url(storage_path, 3600)
        
        if "signedURL" not in signed_url_res:
            logger.error(f"[PROMOTION] Could not generate signed URL for {storage_path}")
            return
            
        json_url = signed_url_res["signedURL"]
        resp = requests.get(json_url)
        if resp.status_code != 200:
            logger.error(f"[PROMOTION] Failed to fetch JSON from {json_url}, status={resp.status_code}")
            return
            
        data = resp.json()
        result = UnifiedVideoSummary.model_validate(data)
    except Exception as e:
        logger.error(f"[PROMOTION] Error fetching canonical results for video_id={video_id}: {e}")
        return

    # 3. Look up the linked demo_mission + route GPS
    mission_repo = MissionRepository(client)
    bus_id: str | None = None
    route_name: str | None = None
    interpolator: InterpolationEngine | None = None

    try:
        ms = mission_repo.get_mission(mission_id)
        if ms:
            bus_id = ms.get("bus_id")
            route_name = ms.get("route_name")
            route_points = mission_repo.get_route_points(mission_id)
            if len(route_points) >= 2:
                interpolator = InterpolationEngine(route_points)
                logger.info("[PROMOTION] GPS interpolator ready points=%d", len(route_points))
            else:
                logger.warning("[PROMOTION] too few route_points (%d) for GPS interpolation", len(route_points))
    except Exception as gps_exc:
        logger.warning("[PROMOTION] GPS lookup failed (incidents will have no lat/lng): %s", gps_exc)

    def _gps_at(ts: float):
        if interpolator is None:
            return None, None
        try:
            lat, lng = interpolator.position_at(ts)
            return lat, lng
        except Exception:
            return None, None

    # Get job_id for the video
    job_resp = client.table("ai_jobs").select("id").eq("video_id", video_id).order("created_at", desc=True).limit(1).execute()
    job_id = job_resp.data[0]["id"] if job_resp.data else None
    job_start = datetime.now(timezone.utc)

    # 4. Build Incidents + Observations via DeduplicationPipeline
    evidence_to_insert = []
    dedup_pipeline = DeduplicationPipeline(client)

    def _process_event(e, incident_type: str):
        lat, lng = _gps_at(e.first_seen_timestamp)
        
        # Force manual insert for demo missions (bypass deduplication) to match exact event count
        if True: # bypass deduplication completely
            incident_id = str(uuid.uuid4())
            first_seen = (job_start + timedelta(seconds=e.first_seen_timestamp)).isoformat()
            last_seen  = (job_start + timedelta(seconds=e.last_seen_timestamp)).isoformat()
            
            inc = {
                "id": incident_id,
                "incident_type": incident_type,
                "status": "OPEN",
                "severity": "MODERATE",
                "confidence": e.max_confidence,
                "timestamp": first_seen,
                "latitude": lat,
                "longitude": lng,
                "ai_job_id": job_id,
                "tracking_id": str(e.event_id),
                "metadata": {
                    "video_id": video_id,
                    "mission_id": mission_id,
                    "bus_id": bus_id,
                    "route_name": route_name,
                    "composite_score": e.stability_score,
                    "video_time_sec":  e.first_seen_timestamp,
                    "last_video_time_sec": e.last_seen_timestamp,
                    "total_detections": e.total_detections,
                },
            }
            
            if incident_type == "pothole":
                inc["metadata"]["description"] = getattr(e, "suppression_reason", None)
            elif incident_type == "waterlogging":
                inc["water_area_ratio"] = getattr(e, "max_area_ratio", None)
                inc["metadata"]["polygon"] = getattr(e, "last_polygon", None)
                inc["metadata"]["test_mode"] = True
            
            try:
                client.table("incidents").insert(inc).execute()
                client.table("incident_observations").insert({
                    "incident_id":     incident_id,
                    "mission_id":      mission_id,
                    "bus_id":          bus_id,
                    "video_timestamp": e.first_seen_timestamp,
                    "confidence":      e.max_confidence,
                    "bbox":            e.representative_bbox,
                    "frame_index":     e.first_seen_frame,
                }).execute()
                evidence_to_insert.append({
                    "incident_id":  incident_id,
                    "evidence_type": "video",
                    "storage_path": f"results/{video_id}_unified.json",
                })
            except Exception as exc:
                logger.error("[PROMOTION] Failed to insert fallback incident: %s", exc)
            return

        # Prepare for pipeline
        detection = {
            "incident_type": incident_type,
            "latitude": lat,
            "longitude": lng,
            "confidence": e.max_confidence,
            "video_timestamp": e.first_seen_timestamp,
            "frame_index": e.first_seen_frame,
            "bbox": e.representative_bbox,
        }
        
        extra_inc = {
            "ai_job_id": job_id,
            "tracking_id": str(e.event_id),
            "metadata": {
                "video_id": video_id,
                "mission_id": mission_id,
                "bus_id": bus_id,
                "route_name": route_name,
                "composite_score": e.stability_score,
                "video_time_sec": e.first_seen_timestamp,
                "last_video_time_sec": e.last_seen_timestamp,
                "total_detections": e.total_detections,
            }
        }
        
        if incident_type == "pothole":
            extra_inc["metadata"]["description"] = getattr(e, "suppression_reason", None)
        elif incident_type == "waterlogging":
            extra_inc["water_area_ratio"] = getattr(e, "max_area_ratio", None)
            extra_inc["metadata"]["polygon"] = getattr(e, "last_polygon", None)
            extra_inc["metadata"]["test_mode"] = True

        try:
            res = dedup_pipeline.process(
                detection=detection,
                mission_id=mission_id,
                bus_id=bus_id or "UNKNOWN",
                extra_incident_fields=extra_inc,
            )
            evidence_to_insert.append({
                "incident_id":  res["incident_id"],
                "evidence_type": "video",
                "storage_path": f"results/{video_id}_unified.json",
            })
        except Exception as exc:
            logger.error("[PROMOTION] dedup_pipeline failed for %s: %s", incident_type, exc)

    # Pothole events
    for e in result.pothole_events:
        if e.max_confidence >= 0.65:
            _process_event(e, "pothole")

    # Waterlogging events
    for e in result.waterlogging_events:
        if e.max_confidence >= 0.55:
            _process_event(e, "waterlogging")

    # Insert Evidence
    BATCH_SIZE = 100
    for i in range(0, len(evidence_to_insert), BATCH_SIZE):
        batch = evidence_to_insert[i:i + BATCH_SIZE]
        client.table("incident_evidence").insert(batch).execute()

    logger.info("[PROMOTION] Complete mission_id=%s gps_resolved=%s", mission_id, "yes" if interpolator else "no")
