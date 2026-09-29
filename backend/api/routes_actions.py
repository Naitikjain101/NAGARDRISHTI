import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.supabase_client import get_supabase
from datetime import datetime, timezone
from api.auth_middleware import require_authenticated, require_maintenance, require_admin, require_control_room
from fastapi import Depends

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
    mapping = {
        "pothole": "Roads & Infrastructure Dept.",
        "road_damage": "Roads & Infrastructure Dept.",
        "waterlogging": "Drainage & Water Management Dept.",
        "traffic_infrastructure": "Traffic Engineering Dept.",
        "hazard": "Emergency Field Response Dept."
    }
    return mapping.get(incident_type.lower(), "Field Operations Dept.")

def get_team_for_incident(incident_type: str) -> Optional[str]:
    mapping = {
        "pothole": "Road Repair Squad",
        "waterlogging": "Drainage Response Team",
        "traffic_infrastructure": "Traffic Ops Team",
    }
    return mapping.get(incident_type.lower(), None)


@router.get("/actions")
async def list_actions(current_user: dict = Depends(require_authenticated)):
    """List all open maintenance actions."""
    client = get_supabase()
    try:
        # Fetch actions and incidents separately to bypass PostgREST schema cache relationship issues
        actions_resp = client.table('maintenance_actions').select('*').execute()
        actions = actions_resp.data
        
        if not actions:
            return []
            
        incident_ids = [a['incident_id'] for a in actions if a.get('incident_id')]
        incidents = []
        if incident_ids:
            inc_resp = client.table('incidents').select('*').in_('id', incident_ids).execute()
            incidents = inc_resp.data
            
        inc_map = {inc['id']: inc for inc in incidents}
        
        for action in actions:
            if action.get('incident_id'):
                action['incidents'] = inc_map.get(action['incident_id'])
                
        return actions
    except Exception as e:
        logger.error(f"Failed to fetch actions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch actions")

@router.get("/actions/{action_id}")
async def get_action(action_id: str, current_user: dict = Depends(require_authenticated)):
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
async def get_incident_action(incident_id: str, current_user: dict = Depends(require_authenticated)):
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
async def create_action(incident_id: str, current_user: dict = Depends(require_control_room)):
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
            "status": "ASSIGNED",
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
async def update_action(action_id: str, update_data: ActionUpdate, current_user: dict = Depends(require_maintenance)):
    """Update maintenance action status."""
    client = get_supabase()
    try:
        now = get_current_utc()
        payload = {
            "status": update_data.status,
            "updated_at": now
        }
        
        if update_data.status == "ASSIGNED":
            payload["assigned_at"] = now
            payload["assigned_team"] = "Road Repair Squad"
            payload["assigned_department"] = "Roads & Infrastructure Dept."
            
        elif update_data.status == "IN_PROGRESS":
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
        
        # Sync incident status if resolving/rejecting/in_progress/assigned
        if update_data.status in ["ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"]:
            client.table("incidents").update({"status": update_data.status}).eq("id", res.data[0]["incident_id"]).execute()
            
        return action_record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update action {action_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
