import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from db.supabase_client import get_supabase
from db.repository import BusRepository, BusTelemetryRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/buses", tags=["fleet"])

@router.get("/")
async def list_buses():
    """List all buses with their latest telemetry and journeys."""
    client = get_supabase()
    bus_repo = BusRepository(client)
    telem_repo = BusTelemetryRepository(client)
    
    buses = bus_repo.get_all()
    
    # Fetch recent telemetry
    recent_telem = telem_repo.get_latest_all()
    telem_map = {}
    for t in recent_telem:
        if t['bus_id'] not in telem_map:
            telem_map[t['bus_id']] = t
            
    # Fetch demo_missions (journeys) for these buses
    missions_resp = client.table("demo_missions").select("*").execute()
    missions = missions_resp.data if missions_resp.data else []
    
    missions_by_bus = {}
    for m in missions:
        bus_id = m['bus_id']
        if bus_id not in missions_by_bus:
            missions_by_bus[bus_id] = []
        missions_by_bus[bus_id].append(m)
            
    # Attach telemetry and journeys
    for b in buses:
        b['latest_telemetry'] = telem_map.get(b['id'])
        # Map by fleet_number since demo_missions.bus_id stores fleet_number
        b['journeys'] = missions_by_bus.get(b['fleet_number'], [])
        
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

@router.get("/analytics/summary")
async def get_fleet_summary():
    """Return fleet KPIs, coverage, and incident metrics for Phase 6."""
    client = get_supabase()
    
    # 1. Fleet Stats
    buses_res = client.table("buses").select("id", count="exact").execute()
    total_buses = buses_res.count if buses_res.count else 0
    
    missions_res = client.table("demo_missions").select("id", count="exact").execute()
    total_journeys = missions_res.count if missions_res.count else 0
    
    # 2. Coverage Stats
    # For Phase 6, compute total points in route_points as a rough estimate
    # 1 route point is approx 5-10 meters. We will use a simplified calculation.
    # We will get unique route names from demo_missions
    m_res = client.table("demo_missions").select("route_name").execute()
    routes = m_res.data if m_res.data else []
    # Just mock coverage based on points to avoid expensive geometry in Python,
    # or fetch point count.
    pts_res = client.table("route_points").select("id", count="exact").execute()
    total_points = pts_res.count if pts_res.count else 0
    
    # Assume ~5m per point. 
    # observed_route_km = total_points * 5 / 1000
    # For demo, let's say total_route_km is 100km.
    observed_km = round(total_points * 5 / 1000, 2)
    total_km = max(observed_km, 100.0) # Base denominator
    
    # 3. Incident Stats
    inc_res = client.table("incidents").select("id, status, dedup_status, severity, maintenance_actions(status)").execute()
    incidents = inc_res.data if inc_res.data else []
    
    total_incidents = len(incidents)
    
    def is_resolved(inc):
        actions = inc.get("maintenance_actions")
        if not actions:
            return False
        if isinstance(actions, list) and len(actions) > 0:
            return actions[0].get("status") == "RESOLVED"
        if isinstance(actions, dict):
            return actions.get("status") == "RESOLVED"
        return False
        
    open_incidents = len([i for i in incidents if i.get("status") == "OPEN" and not is_resolved(i)])
    confirmed_incidents = len([i for i in incidents if i.get("dedup_status") == "CONFIRMED" and not is_resolved(i)])
    validated_incidents = len([i for i in incidents if i.get("dedup_status") != "REJECTED"])
    critical_incidents = len([i for i in incidents if (i.get("severity") or "").upper() == "CRITICAL" and not is_resolved(i)])
    
    return {
        "fleet": {
            "total_buses": total_buses,
            "active_journeys": total_journeys
        },
        "coverage": {
            "total_route_km": total_km,
            "observed_route_km": observed_km,
            "coverage_percent": round((observed_km / total_km) * 100, 1) if total_km > 0 else 0
        },
        "incidents": {
            "total": total_incidents,
            "open": open_incidents,
            "validated": validated_incidents,
            "confirmed": confirmed_incidents,
            "critical": critical_incidents
        }
    }

