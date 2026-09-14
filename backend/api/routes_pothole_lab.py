"""
Urban Watch — Pothole Lab API Routes

Phase 19 Safety Update:
- The /analyze endpoint now accepts `model_id` (from the registry) rather than
  an arbitrary `model_path` string. The backend resolves model_id → trusted path.
- This prevents the frontend from accessing arbitrary filesystem paths.
- `video_path` remains an absolute path string (intentional — lab needs to target
  pre-existing test videos without re-uploading them each time).
"""

import logging
from typing import Dict, Any, Optional
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai.pothole.lab_processor import PotholeLabProcessor
from ai.models.registry import get_all_models, get_active_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pothole-lab", tags=["pothole-lab"])

# In-memory result cache for the lab session
_LAB_CACHE: Dict[str, Dict[str, Any]] = {}


class AnalyzeRequest(BaseModel):
    video_path: str
    # model_id resolves to a registry entry — never an arbitrary filesystem path.
    # Defaults to None → uses currently active POTHOLE model from registry.
    model_id: Optional[str] = None
    confidence: float = 0.10
    use_tracking: bool = True
    job_id: str


@router.post("/upload")
async def upload_custom_video(file: UploadFile = File(...)):
    """
    Upload a custom video specifically for the lab.
    Returns the absolute path to the saved video.
    """
    lab_dir = Path("uploads/lab")
    lab_dir.mkdir(parents=True, exist_ok=True)

    video_id = str(uuid.uuid4())
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    dest_path = lab_dir / f"{video_id}{suffix}"

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"status": "success", "video_path": str(dest_path.absolute())}


@router.get("/stream")
async def stream_video(path: str):
    """
    Stream a video file from an absolute path on the backend.
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(path, media_type="video/mp4")


@router.post("/analyze")
async def analyze_video(req: AnalyzeRequest):
    """
    Run the isolated lab processor on the given video.

    model_id is resolved via the registry — the frontend never controls the path.
    """
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail=f"Video not found: {req.video_path}")

    # Resolve model_id → trusted registry path
    try:
        if req.model_id:
            pothole_models = get_all_models().get("POTHOLE", {})
            if req.model_id not in pothole_models:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown pothole model_id: {req.model_id}. "
                           f"Valid IDs: {list(pothole_models)}"
                )
            entry = pothole_models[req.model_id]
            if not entry.get("file_exists", False):
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{req.model_id}' file is not present on disk."
                )
            model_path = entry["model_path"]
        else:
            # Use the currently active pothole model from the registry
            active = get_active_model("POTHOLE")
            model_path = active["model_path"]

        logger.info(
            "Pothole Lab: Processing %s with model_id=%s path=%s",
            req.video_path, req.model_id or "active", model_path,
        )

        processor = PotholeLabProcessor(model_path=model_path, confidence=req.confidence)
        result = processor.process(req.video_path, use_tracking=req.use_tracking)

        # Annotate result with resolved model info
        result["metadata"]["model_id"] = req.model_id or "active"
        result["metadata"]["model_path"] = model_path

        _LAB_CACHE[req.job_id] = result

        return {"status": "success", "job_id": req.job_id, "frames_count": len(result["frames"])}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Pothole Lab Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """
    Fetch the results of a lab analysis session.
    """
    if job_id not in _LAB_CACHE:
        raise HTTPException(status_code=404, detail="Job results not found in lab cache.")
    return _LAB_CACHE[job_id]
