import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from db.supabase_client import get_supabase
from db.repository import NotificationRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/")
async def get_notifications(limit: int = Query(default=20)):
    """List recent notifications."""
    client = get_supabase()
    repo = NotificationRepository(client)
    return repo.get_recent(limit)

@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str):
    """Mark a notification as read."""
    client = get_supabase()
    repo = NotificationRepository(client)
    
    success = repo.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success"}
