import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.supabase_client import get_supabase
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["maintenance_actions"])

def get_current_utc():
    return datetime.now(timezone.utc).isoformat()

class ActionCreate(BaseModel):
    pass # Currently no body required since type is inferred from incident, but could take optional overrides

class ActionUpdate(BaseModel):
    status: str
    resolution_note: Optional[str] = None

# Helpers for deterministic mapping
def get_action_type_for_incident(incident_type: str) -> str:
    mapping = {
        "pothole": "Road inspection / pothole repair",
        "road_damage": "Road maintenance inspection",
        "waterlogging": "Drainage inspection / waterlogging response",
        "traffic_infrastructure": "Traffic infrastructure inspection",
        "hazard": "Road hazard response"
    }
    return mapping.get(incident_type.lower(), "Field inspection required")

def get_department_for_incident(incident_type: str) -> Optional[str]:
    # No longer hardcoded default departments to allow UNASSIGNED detection
    return None

def get_team_for_incident(incident_type: str) -> Optional[str]:
    # No longer hardcoded default teams to allow UNASSIGNED detection
    return None


@router.get("/actions")
async def list_actions():
    """List all open maintenance actions."""
    client = get_supabase()
    try:
        # Fetch actions with their incidents
        response = client.table('maintenance_actions').select('*, incidents(*)').execute()
        return response.data
    except Exception as e:
        logger.error(f"Failed to fetch actions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch actions")

@router.get("/actions/{action_id}")
async def get_action(action_id: str):
    client = get_supabase()
    try:
        response = client.table('maintenance_actions').select('*').eq('id', action_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Action not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch action {action_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch action")

@router.get("/incidents/{incident_id}/actions")
async def get_incident_action(incident_id: str):
    """Fetch the maintenance action for a specific incident."""
    client = get_supabase()
    try:
        response = client.table('maintenance_actions').select('*').eq('incident_id', incident_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="No action found for this incident")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch action for incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/incidents/{incident_id}/actions")
async def create_action(incident_id: str):
    """Create a new maintenance action for an incident."""
    client = get_supabase()
    try:
        existing = client.table('maintenance_actions').select('*').eq('incident_id', incident_id).execute()
        if existing.data:
            return existing.data[0]

        # Fetch incident to determine type
        inc_res = client.table('incidents').select('incident_type').eq('id', incident_id).execute()
        if not inc_res.data:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        incident_type = inc_res.data[0].get('incident_type', '')

        # Build action
        now = get_current_utc()
        action_payload = {
            "incident_id": incident_id,
            "status": "UNASSIGNED", # Properly unassigned
            "assigned_department": get_department_for_incident(incident_type),
            "assigned_team": get_team_for_incident(incident_type),
            "action_type": get_action_type_for_incident(incident_type),
            "assigned_at": now,
            "created_at": now,
            "updated_at": now
        }

        # Save to DB
        res = client.table('maintenance_actions').insert(action_payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create action")
        
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create action for incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.patch("/actions/{action_id}")
async def update_action(action_id: str, update_data: ActionUpdate):
    """Update maintenance action status."""
    client = get_supabase()
    try:
        now = get_current_utc()
        payload = {
            "status": update_data.status,
            "updated_at": now
        }
        
        if update_data.status == "IN_PROGRESS":
            payload["started_at"] = now
            
        elif update_data.status == "RESOLVED":
            if not update_data.resolution_note:
                raise HTTPException(status_code=400, detail="Resolution note is required for RESOLVED status")
            payload["resolved_at"] = now
            payload["resolution_note"] = update_data.resolution_note
            
        elif update_data.status == "REJECTED":
            if update_data.resolution_note:
                payload["resolution_note"] = update_data.resolution_note

        res = client.table('maintenance_actions').update(payload).eq('id', action_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Action not found or update failed")
            
        action_record = res.data[0]
        
        # Sync RESOLVED status to the Incident
        if update_data.status == "RESOLVED" and action_record.get('incident_id'):
            client.table('incidents').update({"status": "RESOLVED"}).eq('id', action_record['incident_id']).execute()
            
        return action_record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update action {action_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
