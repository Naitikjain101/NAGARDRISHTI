import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.supabase_client import get_supabase
from db.repository import MaintenanceRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

class MaintenanceTaskCreate(BaseModel):
    incident_id: Optional[str] = None
    road_segment_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: Optional[str] = "MODERATE"

class MaintenanceTaskUpdate(BaseModel):
    status: str
    resolution_notes: Optional[str] = None

@router.get("/")
async def list_tasks():
    """List all maintenance tasks."""
    client = get_supabase()
    repo = MaintenanceRepository(client)
    return repo.get_all()

@router.post("/")
async def create_task(task_data: MaintenanceTaskCreate):
    """Create a new maintenance task."""
    client = get_supabase()
    repo = MaintenanceRepository(client)
    
    payload = task_data.dict(exclude_unset=True)
    record = repo.create(payload)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to create maintenance task")
    return record

@router.patch("/{task_id}")
async def update_task(task_id: str, update_data: MaintenanceTaskUpdate):
    """Update maintenance task status."""
    client = get_supabase()
    repo = MaintenanceRepository(client)
    
    success = repo.update_status(task_id, update_data.status, update_data.resolution_notes)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or update failed")
    return {"status": "success"}
