"""
Urban Watch — AI API Routes

POST /api/ai/process/{video_id}
GET  /api/ai/results/{video_id}
GET  /api/ai/status/{video_id}
GET  /api/ai/device
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from ai.common.device import get_device_info
from ai.common.schemas import (
    AIStatusResponse,
    DeviceResponse,
    ProcessingStatus,
)
from db.supabase_client import get_supabase
from db.repository import AIJobRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Populated by main.py
UPLOAD_DIR: Path = Path("uploads")
RESULTS_DIR: Path = Path("results")

def set_directories(upload_dir: Path, results_dir: Path) -> None:
    global UPLOAD_DIR, RESULTS_DIR
    UPLOAD_DIR = upload_dir
    RESULTS_DIR = results_dir

@router.get("/device", response_model=DeviceResponse)
async def get_device():
    """Return the active compute device information."""
    info = get_device_info()
    return DeviceResponse(
        device=info.device_str,
        device_name=info.device_name,
        cuda_available=info.cuda_available,
        mps_available=info.mps_available,
        torch_version=info.torch_version,
    )

from ai.models.registry import get_all_models, set_active_model, rollback_active_model
from pydantic import BaseModel

from typing import Optional

class ModelSwitchRequest(BaseModel):
    task: str
    model_id: str
    confidence_threshold: Optional[float] = None

class ModelConfidenceUpdateRequest(BaseModel):
    task: str
    model_id: str
    confidence_threshold: float

@router.get("/models")
async def get_models():
    """Return all registered models with active/previous/file_exists flags."""
    return get_all_models()

@router.get("/models/{task}")
async def get_task_models(task: str):
    """Return models for a single task."""
    all_models = get_all_models()
    task_upper = task.upper()
    if task_upper not in all_models:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task}")
    return all_models[task_upper]

@router.post("/models/active")
async def switch_active_model(req: ModelSwitchRequest):
    """
    Switch the active model for a task (by model_id).

    The frontend sends only model_id — the backend resolves it to a
    trusted registry path. Does NOT reload running model cache;
    takes effect on next server start or explicit reload.
    """
    try:
        set_active_model(req.task, req.model_id, req.confidence_threshold)
        return {
            "status": "success",
            "message": f"Switched {req.task} → {req.model_id}",
            "note": "Restart server or reload cache for change to take effect in processing pipeline."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/confidence")
async def update_model_confidence(req: ModelConfidenceUpdateRequest):
    """
    Update the confidence threshold for a specific task and model without switching.
    """
    try:
        set_active_model(req.task, req.model_id, req.confidence_threshold)
        return {
            "status": "success",
            "message": f"Updated confidence for {req.task} ({req.model_id}) to {req.confidence_threshold}",
            "note": "Takes effect for new video processing jobs."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/rollback/{task}")
async def rollback_model(task: str):
    """
    Rollback the active model for a task to its previous selection.

    Safe: only changes the active model ID config — does NOT delete data,
    reprocess videos, or modify incidents/journeys/evidence.
    """
    try:
        prev_model_id = rollback_active_model(task.upper())
        if prev_model_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"No previous model selection found for task {task}."
            )
        return {
            "status": "success",
            "task": task.upper(),
            "rolled_back_to": prev_model_id,
            "note": "Restart server or reload cache for change to take effect in processing pipeline."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/process/{video_id}")
async def process_video(video_id: str, background_tasks: BackgroundTasks):
    """
    Start AI processing for an uploaded video.
    Runs in background — returns immediately.
    """
    video_path = _find_video(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not found")

    client = get_supabase()
    repo = AIJobRepository(client)
    
    # Optional: check if job already exists and is running
    # Since we use video_id in the url, we will just create a new ai_job record
    job_data = {
        "video_id": video_id,
        "status": ProcessingStatus.PENDING,
        "device": get_device_info().device_str
    }
    
    job_record = repo.create(job_data)
    if not job_record:
        raise HTTPException(status_code=500, detail="Failed to initialize AI Job in database")
        
    job_id = job_record["id"]

    background_tasks.add_task(
        _run_processing,
        job_id=job_id,
        video_id=video_id,
        video_path=str(video_path),
    )

    return {
        "message": "Processing started",
        "job_id": job_id,
        "video_id": video_id,
        "status": ProcessingStatus.RUNNING,
    }

@router.get("/status/{video_id}", response_model=AIStatusResponse)
async def get_processing_status(video_id: str):
    """
    Return current AI processing status for a video.
    Since one video could have multiple jobs, we return the latest job's status.
    """
    client = get_supabase()
    
    # Query latest job for this video
    try:
        response = client.table("ai_jobs").select("*").eq("video_id", video_id).order("created_at", desc=True).limit(1).execute()
        job_info = response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Failed to fetch job status: {e}")
        job_info = None

    if not job_info:
        # Check if legacy results already exist
        result_path = RESULTS_DIR / f"{video_id}.json"
        if result_path.exists():
            return AIStatusResponse(
                video_id=video_id,
                status=ProcessingStatus.COMPLETE,
            )
        return AIStatusResponse(
            video_id=video_id,
            status=ProcessingStatus.PENDING,
        )

    return AIStatusResponse(
        video_id=video_id,
        status=job_info["status"],
        progress_frames=job_info.get("frames_processed", 0),
        total_frames=job_info.get("total_frames", 0),
        error=job_info.get("error"),
    )

@router.get("/results/{video_id}")
async def get_results(video_id: str):
    """
    Return AI detection results for a processed video.
    """
    result_path = RESULTS_DIR / f"{video_id}.json"

    if not result_path.exists():
        client = get_supabase()
        try:
            response = client.table("ai_jobs").select("*").eq("video_id", video_id).order("created_at", desc=True).limit(1).execute()
            job_info = response.data[0] if response.data else None
        except:
            job_info = None

        if job_info and job_info["status"] == ProcessingStatus.RUNNING:
            raise HTTPException(
                status_code=202,
                detail="Processing in progress — poll /api/ai/status/{video_id}",
            )

        raise HTTPException(
            status_code=404,
            detail="Results not found. Process the video first via POST /api/ai/process/{video_id}",
        )

    try:
        with open(result_path, "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read results: {exc}",
        )

def _run_processing(job_id: str, video_id: str, video_path: str) -> None:
    """
    Background task: runs UnifiedVideoProcessor (same as Fleet pipeline).
    
    Phase 12.5 Fix: both Video Analyze and Fleet now use the SAME processor,
    the SAME model (yolo26m_pothole_best.pt SHA 8e5da7c4), and the SAME thresholds.
    """
    client = get_supabase()
    repo = AIJobRepository(client)
    
    repo.update_status(job_id=job_id, status=ProcessingStatus.RUNNING)

    def progress_callback(done: int, total: int, **kwargs) -> None:
        if done % 10 == 0 or done == total:
            repo.update_status(
                job_id=job_id,
                status=ProcessingStatus.RUNNING,
                progress_frames=done,
                total_frames=total,
            )

    try:
        from ai.unified.processor import UnifiedVideoProcessor
        from ai.unified.schemas import UnifiedVideoSummary

        processor = UnifiedVideoProcessor()
        result: UnifiedVideoSummary = processor.process(
            video_path=video_path,
            video_id=video_id,
            results_dir=str(RESULTS_DIR),
            progress_callback=progress_callback,
        )

        from ai.common.schemas import ProcessingStatus as PS
        final_status = (
            PS.COMPLETE
            if result.status in (PS.COMPLETED, PS.COMPLETE)
            else PS.FAILED
        )

        client.table("ai_jobs").update({
            "status": final_status,
            "error": result.error if hasattr(result, "error") else None,
            "frames_processed": result.processing.total_frames if result.processing else None,
            "completed_at": "now()"
        }).eq("id", job_id).execute()

        logger.info("Processing complete: %s — status=%s potholes=%d", video_id, final_status, len(result.pothole_events or []))

    except Exception as exc:
        logger.error("Processing failed for %s: %s", video_id, exc, exc_info=True)
        client.table("ai_jobs").update({
            "status": ProcessingStatus.FAILED,
            "error": str(exc),
            "completed_at": "now()"
        }).eq("id", job_id).execute()


def _find_video(video_id: str) -> Path | None:
    """Find uploaded video file by video_id."""
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        path = UPLOAD_DIR / f"{video_id}{suffix}"
        if path.exists():
            return path
    return None
