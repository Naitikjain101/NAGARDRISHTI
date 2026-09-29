import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from db.supabase_client import get_supabase
from db.repository import IncidentRepository
from api.auth_middleware import require_authenticated, require_control_room
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/incidents", tags=["incidents"])

class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    validation_status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("/")
async def create_incident(incident_data: Dict[str, Any] = Body(...), current_user: dict = Depends(require_control_room)):
    """Create or upsert an incident."""
    client = get_supabase()
    repo = IncidentRepository(client)
    # Extract observation data if provided
    observation_data = incident_data.pop("observation", None)
    
    created = repo.create(incident_data)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create incident")
        
    if observation_data:
        try:
            observation_data["incident_id"] = created["id"]
            if "created_at" not in observation_data:
                import datetime
                observation_data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Remove keys that are not in the schema
            observation_data.pop("video_filename", None)
            observation_data.pop("metadata", None)
            
            client.table("incident_observations").insert(observation_data).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save observation: {e}")
            
    try:
        from api.routes_actions import get_action_type_for_incident
        action_type = get_action_type_for_incident(created.get("incident_type", ""))
        action_data = {
            "incident_id": created["id"],
            "status": "UNASSIGNED",
            "action_type": action_type,
        }
        client.table("maintenance_actions").upsert(action_data, on_conflict="incident_id").execute()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to auto-create maintenance action: {e}")

    return _record_to_dict(created)

def _record_to_dict(inc: dict) -> dict:
    """Convert Supabase dict to API response dict matching the new schema."""
    return {
        "id": inc.get("id"),
        "ai_job_id": inc.get("ai_job_id"),
        "type": inc.get("incident_type"),
        "incident_type": inc.get("incident_type"),
        "severity": inc.get("severity"),
        "status": inc.get("status"),
        "confidence": inc.get("confidence"),
        "model_name": inc.get("model_name"),
        "model_version": inc.get("model_version"),
        "timestamp": inc.get("timestamp"),
        "frame_index": inc.get("frame_index"),
        "bus_id": inc.get("bus_id"),
        "camera_id": inc.get("camera_id"),
        "latitude": inc.get("latitude"),
        "longitude": inc.get("longitude"),
        "road_segment_id": inc.get("road_segment_id"),
        "validation_status": inc.get("validation_status"),
        "water_area_ratio": inc.get("water_area_ratio"),
        "bbox": inc.get("bbox"),
        "tracking_id": inc.get("tracking_id"),
        "vehicle_class": inc.get("vehicle_class"),
        "metadata": inc.get("metadata"),
        "first_seen_at": inc.get("first_seen_at"),
        "last_seen_at": inc.get("last_seen_at"),
        "observation_count": inc.get("observation_count"),
        "observed_by": inc.get("observed_by"),
        "dedup_status": inc.get("dedup_status"),
        "priority_score": inc.get("priority_score"),
        "priority_level": inc.get("priority_level"),
        "priority_breakdown": inc.get("priority_breakdown"),
        "created_at": inc.get("created_at"),
        "updated_at": inc.get("updated_at")
    }

@router.get("/")
async def list_incidents(
    incident_type: Optional[str] = Query(default=None, description="Filter by type: pothole, no_helmet, helmet, waterlogging, vehicle"),
    status: Optional[str] = Query(default=None, description="Filter by status: OPEN, ASSIGNED, RESOLVED, DISMISSED"),
    severity: Optional[str] = Query(default=None, description="Filter by severity: LOW, MODERATE, HIGH, CRITICAL"),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    job_id: Optional[str] = Query(default=None, description="Filter by AI Job ID"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_authenticated)
):
    """
    List incidents from all processed jobs.
    Supports filtering and pagination.
    """
    client = get_supabase()
    repo = IncidentRepository(client)
    
    incidents = repo.get_filtered(
        incident_type=incident_type,
        status=status,
        severity=severity,
        min_confidence=min_confidence,
        job_id=job_id,
        limit=limit,
        offset=offset
    )
    
    total = repo.count_filtered(
        incident_type=incident_type,
        status=status,
        severity=severity,
        min_confidence=min_confidence,
        job_id=job_id
    )

    return {
        "incidents": [_record_to_dict(r) for r in incidents],
        "total": total,
        "page_size": limit,
        "offset": offset
    }

@router.get("/{incident_id}")
async def get_incident(incident_id: str, current_user: dict = Depends(require_authenticated)):
    """Get a single incident by ID."""
    client = get_supabase()
    repo = IncidentRepository(client)
    
    record = repo.get_by_id(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
        
    return _record_to_dict(record)

@router.patch("/{incident_id}")
async def update_incident(incident_id: str, update_data: IncidentUpdate, current_user: dict = Depends(require_control_room)):
    """Update an incident (e.g. status, severity, validation)."""
    client = get_supabase()
    repo = IncidentRepository(client)
    
    record = repo.get_by_id(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
        
    # Build payload
    payload = {}
    if update_data.status is not None:
        payload["status"] = update_data.status
    if update_data.severity is not None:
        payload["severity"] = update_data.severity
    if update_data.validation_status is not None:
        payload["validation_status"] = update_data.validation_status
    if update_data.metadata is not None:
        # Merge metadata
        current_meta = record.get("metadata") or {}
        current_meta.update(update_data.metadata)
        payload["metadata"] = current_meta
        
    if not payload:
        return _record_to_dict(record)
        
    from datetime import datetime, timezone
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    response = client.table("incidents").update(payload).eq("id", incident_id).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update incident")
        
    return _record_to_dict(response.data[0])
