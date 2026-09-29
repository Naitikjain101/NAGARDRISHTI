from fastapi import APIRouter, HTTPException
from typing import List
from ai.unified.schemas import UnifiedPotholeEvent

router = APIRouter(prefix="/api/events", tags=["events"])

# In a real system, these would come from a database.
# For Phase 5, we'll keep an in-memory store that the processor can populate.
IN_MEMORY_EVENTS: List[UnifiedPotholeEvent] = []

@router.get("", response_model=List[UnifiedPotholeEvent])
def get_all_events():
    return IN_MEMORY_EVENTS

@router.get("/potholes", response_model=List[UnifiedPotholeEvent])
def get_pothole_events():
    return [e for e in IN_MEMORY_EVENTS if e.event_type == "pothole"]

@router.get("/no-helmet", response_model=List[UnifiedPotholeEvent])
def get_no_helmet_events():
    return [e for e in IN_MEMORY_EVENTS if e.event_type == "no_helmet"]

@router.get("/{event_id}", response_model=UnifiedPotholeEvent)
def get_event_by_id(event_id: int):
    for e in IN_MEMORY_EVENTS:
        if e.event_id == event_id:
            return e
    raise HTTPException(status_code=404, detail="Event not found")
