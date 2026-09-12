import logging
from typing import Dict, Any
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai.pothole.lab_processor import PotholeLabProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pothole-lab", tags=["pothole-lab"])

# We'll cache results in memory for the lab session to avoid constant re-inference
# A more robust solution would write to disk, but for this debug lab, memory is fine
# provided the videos aren't 10 hours long.
_LAB_CACHE: Dict[str, Dict[str, Any]] = {}


class AnalyzeRequest(BaseModel):
    video_path: str
    model_path: str = "runs/detect/models/pothole/v2/weights/best.pt"
    confidence: float = 0.10
    use_tracking: bool = True
    job_id: str


@router.post("/upload")
async def upload_custom_video(file: UploadFile = File(...)):
    """
    Upload a custom video specifically for the lab.
    Returns the absolute path to the saved video.
    """
    # Use a lab-specific folder or just backend/uploads/lab
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
    """
    logger.info(f"Pothole Lab: Processing {req.video_path} with {req.model_path}")
    
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail=f"Video not found: {req.video_path}")
        
    if not os.path.exists(req.model_path):
        raise HTTPException(status_code=404, detail=f"Model not found: {req.model_path}")
        
    try:
        processor = PotholeLabProcessor(model_path=req.model_path, confidence=req.confidence)
        result = processor.process(req.video_path, use_tracking=req.use_tracking)
        
        # Cache it
        _LAB_CACHE[req.job_id] = result
        
        return {"status": "success", "job_id": req.job_id, "frames_count": len(result["frames"])}
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
