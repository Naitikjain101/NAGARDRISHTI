import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from db.supabase_client import get_supabase
from db.repository import BusRepository, BusTelemetryRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/buses", tags=["fleet"])

@router.get("/")
async def list_buses():
    """List all buses with their latest telemetry if available."""
    client = get_supabase()
    bus_repo = BusRepository(client)
    telem_repo = BusTelemetryRepository(client)
    
    buses = bus_repo.get_all()
    
    # In a real heavy DB, we'd do a JOIN. For now, fetch latest 100 telemetry and match.
    recent_telem = telem_repo.get_latest_all()
    telem_map = {}
    for t in recent_telem:
        if t['bus_id'] not in telem_map:
            telem_map[t['bus_id']] = t
            
    # Attach telemetry
    for b in buses:
        b['latest_telemetry'] = telem_map.get(b['id'])
        
    return buses

@router.get("/{bus_id}")
async def get_bus(bus_id: str):
    """Get single bus info."""
    client = get_supabase()
    bus_repo = BusRepository(client)
    telem_repo = BusTelemetryRepository(client)
    
    bus = bus_repo.get_by_id(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
        
    bus['latest_telemetry'] = telem_repo.get_latest_for_bus(bus_id)
    return bus
