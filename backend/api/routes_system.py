import logging
import torch
from fastapi import APIRouter
from db.supabase_client import get_supabase
from db.repository import IncidentRepository, AIJobRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/status")
async def get_system_status():
    """
    Get holistic system status including database counts and CUDA info.
    """
    client = get_supabase()
    
    job_repo = AIJobRepository(client)
    incident_repo = IncidentRepository(client)

    try:
        response = client.table("ai_jobs").select("*", count="exact").execute()
        total_videos = response.count if response.count is not None else 0
        total_incidents = incident_repo.count()
        confirmed_potholes = incident_repo.count_filtered(
            incident_type="pothole", 
            status="confirmed"
        )
        db_status = "ok"
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        db_status = "error"
        total_videos = 0
        total_incidents = 0
        confirmed_potholes = 0

    device = "cpu"
    device_name = "CPU"
    if torch.cuda.is_available():
        device = "cuda"
        device_name = torch.cuda.get_device_name(0)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
        device_name = "Apple Silicon (MPS)"

    return {
        "status": db_status,
        "phase": "5.1",
        "device": device,
        "device_name": device_name,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": hasattr(torch.backends, "mps") and torch.backends.mps.is_available(),
        "torch_version": torch.__version__,
        "ultralytics_version": "8.0+", # simplified
        "total_videos": total_videos,
        "total_incidents": total_incidents,
        "confirmed_potholes": confirmed_potholes,
        "helmet_model_available": True, # assumed for system info
        "ai_disclaimer": "AI detection is for operational intelligence only."
    }
