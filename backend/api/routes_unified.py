"""
Urban Watch — Unified AI API Routes

POST /api/ai/unified/process/{video_id}
GET  /api/ai/unified/results/{video_id}
GET  /api/ai/unified/status/{video_id}
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ai.common.schemas import AIStatusResponse, ProcessingStatus
from ai.unified.processor import UnifiedVideoProcessor

from db.supabase_client import get_supabase
from db.repository import AIJobRepository, IncidentRepository, TrafficWindowRepository, EvidenceRepository
from ai.common.device import get_device_info
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/unified", tags=["ai_unified"])

UPLOAD_DIR: Path = Path("uploads")
RESULTS_DIR: Path = Path("results")

_status_lock = threading.Lock()


def set_directories(upload_dir: Path, results_dir: Path) -> None:
    global UPLOAD_DIR, RESULTS_DIR
    UPLOAD_DIR = upload_dir
    RESULTS_DIR = results_dir


DEMO_DIR: Path = Path("demo_videos")

@router.post("/demo/{demo_name}")
async def run_demo_video(demo_name: str):
    """
    Trigger AI processing directly on a pre-existing demo video.
    Bypasses the HTTP upload entirely to ensure zero upload latency.
    """
    demo_path = DEMO_DIR / demo_name
    if not demo_path.exists():
        raise HTTPException(status_code=404, detail=f"Demo video {demo_name} not found in {DEMO_DIR}")
        
    client = get_supabase()
    
    # Generate a unique video_id for this run so it doesn't collide with previous demo runs
    video_id = f"demo_{uuid.uuid4().hex[:8]}"
    
    # Copy the demo video into the uploads directory so the frontend can stream it
    dest_path = UPLOAD_DIR / f"{video_id}{demo_path.suffix}"
    import shutil
    shutil.copy2(demo_path, dest_path)
    
    device_info = get_device_info()
    job_record = client.table("ai_jobs").insert({
        "video_id": video_id,
        "status": ProcessingStatus.QUEUED.value,
        "device": device_info.device_str,
    }).execute()
    
    job_id = job_record.data[0]["id"]
    
    # Start processing thread
    thread = threading.Thread(
        target=_run_processing,
        args=(job_id, video_id, str(dest_path), client),
        daemon=True
    )
    thread.start()
    
    return {
        "job_id": job_id,
        "video_id": video_id,
        "status": ProcessingStatus.QUEUED.value,
        "message": f"Demo processing started for {demo_name}"
    }

@router.post("/process/{video_id}")
async def process_video_unified(video_id: str):
    video_path = _find_video(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not found. Upload the video first.")

    client = get_supabase()

    # DB-Level Idempotency Check — use canonical string values
    existing_job = (
        client.table("ai_jobs")
        .select("id,status")
        .eq("video_id", video_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if existing_job.data:
        status = existing_job.data[0].get("status")
        job_id = existing_job.data[0].get("id")
        if status in ("queued", "running"):
            return {"message": "Already processing", "job_id": job_id, "video_id": video_id, "status": status}
        if status == "completed":
            return {"message": "Already completed", "job_id": job_id, "video_id": video_id, "status": status}

    repo = AIJobRepository(client)
    job_record = repo.create({
        "video_id": video_id,
        "status": ProcessingStatus.QUEUED,
        "device": get_device_info().device_str,
    })
    if not job_record:
        raise HTTPException(status_code=500, detail="Failed to initialize AI Job in database")

    job_id = job_record["id"]
    logger.info("[VIDEO] job=%s upload_saved video_id=%s video_path=%s", job_id, video_id, video_path)

    # Run processing in its own daemon thread, NOT in FastAPI's BackgroundTasks
    # thread pool. This keeps uvicorn's worker threads free to serve /status polls
    # even while MPS/CPU is saturated by AI inference.
    t = threading.Thread(
        target=_run_processing,
        kwargs={"job_id": job_id, "video_id": video_id, "video_path": str(video_path)},
        name=f"ai-processor-{job_id[:8]}",
        daemon=True,
    )
    t.start()

    logger.info("[VIDEO] job=%s job_created status=queued", job_id)

    return {
        "message": "Processing started",
        "job_id": job_id,
        "video_id": video_id,
        "status": ProcessingStatus.QUEUED,
    }


@router.get("/status/{video_id}", response_model=AIStatusResponse)
async def get_processing_status(video_id: str):
    client = get_supabase()
    try:
        response = (
            client.table("ai_jobs")
            .select("*")
            .eq("video_id", video_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        job_info = response.data[0] if response.data else None
    except Exception as e:
        logger.error("[VIDEO] status lookup failed video_id=%s error=%s", video_id, e)
        job_info = None

    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found for this video")

    return AIStatusResponse(
        video_id=video_id,
        status=job_info["status"],
        progress_frames=job_info.get("frames_processed") or 0,
        total_frames=job_info.get("total_frames") or 0,
        processing_fps=job_info.get("processing_fps"),
        error=job_info.get("error"),
    )


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Poll by job_id instead of video_id — more precise."""
    client = get_supabase()
    try:
        response = client.table("ai_jobs").select("*").eq("id", job_id).execute()
        job_info = response.data[0] if response.data else None
    except Exception as e:
        logger.error("[VIDEO] job status lookup failed job_id=%s error=%s", job_id, e)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "job_id": job_id,
        "video_id": job_info.get("video_id"),
        "status": job_info["status"],
        "progress_frames": job_info.get("frames_processed") or 0,
        "total_frames": job_info.get("total_frames") or 0,
        "processing_fps": job_info.get("processing_fps"),
        "error": job_info.get("error"),
        "created_at": job_info.get("created_at"),
        "completed_at": job_info.get("completed_at"),
    }


@router.get("/results/{video_id}")
async def get_results(video_id: str):
    """Return AI results. Returns 202 if processing is not yet complete."""
    client = get_supabase()

    # Check job status first
    try:
        response = (
            client.table("ai_jobs")
            .select("status,error")
            .eq("video_id", video_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        job_info = response.data[0] if response.data else None
    except Exception as e:
        logger.error("[VIDEO] results status check failed video_id=%s error=%s", video_id, e)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    if not job_info:
        raise HTTPException(status_code=404, detail="No job found for this video")

    status = job_info.get("status")
    if status == "failed":
        raise HTTPException(status_code=422, detail=f"Processing failed: {job_info.get('error', 'Unknown error')}")

    if status != "completed":
        return JSONResponse(
            status_code=202,
            content={"detail": "Processing not yet complete", "status": status},
        )

    # Fetch signed URL from Supabase Storage
    from fastapi.responses import RedirectResponse
    bucket = "urban_watch_evidence"
    storage_path = f"results/{video_id}_unified.json"

    try:
        signed_url_res = client.storage.from_(bucket).create_signed_url(storage_path, 3600)
    except Exception as e:
        logger.error("[VIDEO] signed URL creation failed video_id=%s error=%s", video_id, e)
        raise HTTPException(status_code=500, detail="Failed to generate result URL")

    if "signedURL" not in signed_url_res:
        # Try to serve local fallback
        local_path = RESULTS_DIR / f"{video_id}_unified.json"
        if local_path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(str(local_path), media_type="application/json")
        raise HTTPException(status_code=404, detail="Results not found in storage")

    return RedirectResponse(url=signed_url_res["signedURL"])


def _run_processing(job_id: str, video_id: str, video_path: str) -> None:
    """
    Background task: runs UnifiedVideoProcessor to completion.
    All exceptions must be caught, logged, and persisted as status=failed.
    No exception may silently kill this task.
    """
    client = get_supabase()
    repo = AIJobRepository(client)

    logger.info("[VIDEO] job=%s processor_started video_path=%s", job_id, video_path)
    repo.update_status(job_id=job_id, status=ProcessingStatus.RUNNING)

    # Sync demo_missions.status so the Fleet page reflects real progress
    try:
        client.table("demo_missions").update({"status": "PROCESSING"}).eq("metadata->>video_id", video_id).execute()
        logger.info("[VIDEO] job=%s demo_mission_status=PROCESSING video_id=%s", job_id, video_id)
    except Exception as _ms_exc:
        logger.warning("[VIDEO] job=%s failed to set demo_mission PROCESSING: %s", job_id, _ms_exc)

    # Track actual sampled frame count for accurate progress
    _processed_frames_count = [0]
    _total_frames_count = [0]

    def progress_callback(done: int, total: int, fps: float = 0.0, vehicles: int = 0, potholes: int = 0, waterlogging: int = 0) -> None:
        _processed_frames_count[0] = done
        _total_frames_count[0] = total
        if done % 10 == 0 or done == total:
            logger.info("[VIDEO] job=%s frame=%d/%d fps=%.1f", job_id, done, total, fps)
            repo.update_status(
                job_id=job_id,
                status=ProcessingStatus.RUNNING,
                progress_frames=done,
                total_frames=total,
                processing_fps=round(fps, 1) if fps else None,
            )
            # Update telemetry in demo_missions metadata for Live UI
            try:
                ms_resp = client.table("demo_missions").select("metadata").eq("metadata->>video_id", video_id).execute()
                if ms_resp.data:
                    metadata = ms_resp.data[0].get("metadata") or {}
                    metadata["telemetry"] = {
                        "progress_frames": done,
                        "total_frames": total,
                        "processing_fps": round(fps, 1) if fps else None,
                        "vehicles_found": vehicles,
                        "potholes_found": potholes,
                        "waterlogging_found": waterlogging,
                        "eta_seconds": round((total - done) / max(fps, 0.1)) if fps > 0 else 0
                    }
                    client.table("demo_missions").update({"metadata": metadata}).eq("metadata->>video_id", video_id).execute()
            except Exception as e:
                logger.warning("[VIDEO] Failed to update telemetry for video_id=%s: %s", video_id, e)

    try:
        processor = UnifiedVideoProcessor()
        logger.info("[VIDEO] job=%s video_opened", job_id)

        result = processor.process(
            video_path=video_path,
            video_id=video_id,
            results_dir=str(RESULTS_DIR),
            progress_callback=progress_callback,
        )

        logger.info("[VIDEO] job=%s ai_complete status=%s", job_id, result.status)

        final_status = ProcessingStatus.COMPLETED if result.status in (ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETE) else ProcessingStatus.FAILED
        error_msg = result.error if hasattr(result, "error") else None

        if final_status == ProcessingStatus.COMPLETED:
            try:
                _persist_results(client, job_id, video_id, result)
            except Exception as e:
                logger.error("[VIDEO] job=%s persistence failed: %s", job_id, e)
                final_status = ProcessingStatus.FAILED
                error_msg = str(e)

        # Final DB status update with accurate frame counts
        frames_done = _processed_frames_count[0]
        frames_total = _total_frames_count[0]

        client.table("ai_jobs").update({
            "status": final_status,
            "error": error_msg,
            "frames_processed": frames_done,
            "total_frames": frames_total,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        logger.info(
            "[VIDEO] job=%s status=%s frames_processed=%d total_frames=%d",
            job_id, final_status, frames_done, frames_total,
        )
        
        # Update demo_mission status properly
        demo_status = "READY" if final_status == ProcessingStatus.COMPLETED else "FAILED"
        client.table("demo_missions").update({"status": demo_status}).eq("metadata->>video_id", video_id).execute()

    except Exception as exc:
        error_str = str(exc)
        logger.error("[VIDEO] job=%s ERROR %s", job_id, error_str, exc_info=True)
        try:
            client.table("ai_jobs").update({
                "status": ProcessingStatus.FAILED,
                "error": error_str,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()
        except Exception as db_exc:
            logger.error("[VIDEO] job=%s CRITICAL failed to write error status: %s", job_id, db_exc)

        # Sync demo_missions.status to FAILED
        try:
            client.table("demo_missions").update({"status": "FAILED"}).eq("metadata->>video_id", video_id).execute()
            logger.info("[VIDEO] job=%s demo_mission_status=FAILED video_id=%s", job_id, video_id)
        except Exception as _ms_exc:
            logger.warning("[VIDEO] job=%s failed to set demo_mission FAILED: %s", job_id, _ms_exc)



def _persist_results(client, job_id: str, video_id: str, result) -> None:
    """
    Persist incidents, observations, traffic windows, and evidence to Supabase.
    
    KEY FIX (Phase 12.5):
    - GPS interpolated from route_points so incidents appear on map
    - incident_observations rows created so Evidence Trail is NOT blank
    - first_seen_at / last_seen_at set on each incident
    - mission_id stored in incident metadata
    """
    from db.mission_repository import MissionRepository
    from ai.gis.interpolator import InterpolationEngine
    from missions.deduplication import DeduplicationPipeline

    try:
        # ── 0. Upload results JSON to Supabase Storage ─────────────────────────
        bucket = "urban_watch_evidence"
        result_path = RESULTS_DIR / f"{video_id}_unified.json"
        if result_path.exists():
            try:
                with open(result_path, "rb") as f:
                    client.storage.from_(bucket).upload(
                        path=f"results/{video_id}_unified.json",
                        file=f,
                        file_options={"content-type": "application/json"},
                    )
                logger.info("[VIDEO] job=%s results_uploaded_to_storage", job_id)
            except Exception as storage_exc:
                # Do NOT raise here — a storage failure should not kill persistence.
                logger.error("[VIDEO] job=%s storage_upload_failed (continuing): %s", job_id, storage_exc)

        job_start = datetime.now(timezone.utc)

        # ── 1. Batch Insert Traffic Windows ───────────────────────────────────
        traffic_windows = []
        for w in result.density_windows:
            w_start_time = (job_start + timedelta(seconds=w.window_start)).isoformat()
            w_end_time = (job_start + timedelta(seconds=w.window_end)).isoformat()
            traffic_windows.append({
                "ai_job_id": job_id,
                "road_segment_id": None,
                "start_time": w_start_time,
                "end_time": w_end_time,
                "vehicle_count": w.unique_vehicle_count,
                "congestion_level": w.density_level.value,
                "congestion_score": 0.0,
                "vehicle_distribution": w.class_counts,
            })
        if traffic_windows:
            client.table("traffic_windows").insert(traffic_windows).execute()
            logger.info("[VIDEO] job=%s traffic_windows_inserted count=%d", job_id, len(traffic_windows))
            
        logger.info("[VIDEO] job=%s db_persist_complete (incidents deferred until live monitoring)", job_id)

        # Trigger promotion if the video is already linked to a demo mission
        # This handles the case where users add a QUEUED video to Live Monitoring directly from Fleet.
        try:
            ms_resp = client.table("demo_missions").select("id").eq("metadata->>video_id", video_id).execute()
            if ms_resp.data:
                mission_id = ms_resp.data[0]["id"]
                logger.info("[VIDEO] job=%s video is linked to mission_id=%s, promoting canonical results now", job_id, mission_id)
                from missions.promotion import promote_canonical_results
                promote_canonical_results(video_id, mission_id)
        except Exception as promo_exc:
            logger.error("[VIDEO] job=%s failed to auto-promote incidents: %s", job_id, promo_exc)

        # Status update is handled by the caller based on final_status

    except Exception as db_exc:
        logger.error("[VIDEO] job=%s db_persist FAILED: %s", job_id, db_exc, exc_info=True)
        raise  # Re-raise so caller can mark job as failed


def _find_video(video_id: str) -> Path | None:
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        path = UPLOAD_DIR / f"{video_id}{suffix}"
        if path.exists():
            return path
    return None

