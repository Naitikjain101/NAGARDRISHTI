from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import logging
from supabase import Client

# Note: We rely on the raw dictionaries for Supabase payloads. 
# We could map to Pydantic models, but dictionaries match PostgREST well.
# We will use the schemas where applicable for return types or accept them as dicts.

logger = logging.getLogger("urban_watch.db.repository")

def get_current_utc():
    return datetime.now(timezone.utc).isoformat()

class AIJobRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('ai_jobs').select('*').eq('id', job_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch ai_job {job_id}: {e}")
            return None

    def create(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if 'created_at' not in job_data:
                job_data['created_at'] = get_current_utc()
            if 'updated_at' not in job_data:
                job_data['updated_at'] = get_current_utc()
                
            response = self.client.table('ai_jobs').insert(job_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create ai_job: {e}")
            return None

    def update_status(
        self, 
        job_id: str, 
        status: str, 
        progress_frames: Optional[int] = None, 
        total_frames: Optional[int] = None,
        processing_fps: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            update_data = {
                "status": status,
                "updated_at": get_current_utc()
            }
            if progress_frames is not None:
                update_data["frames_processed"] = progress_frames
            if total_frames is not None:
                update_data["total_frames"] = total_frames
            if processing_fps is not None:
                update_data["processing_fps"] = processing_fps

            response = self.client.table('ai_jobs').update(update_data).eq('id', job_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update ai_job status for {job_id}: {e}")
            return None

    def list_all(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('ai_jobs').select('*').order('created_at', desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to list ai_jobs: {e}")
            return []

    def count(self) -> int:
        try:
            response = self.client.table('ai_jobs').select('id', count='exact').execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Failed to count ai_jobs: {e}")
            return 0


class IncidentRepository:
    def __init__(self, client: Client):
        self.client = client

    def create(self, incident_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # Handle geometry point for PostGIS if lat/lon exist
            lat = incident_data.get('latitude')
            lon = incident_data.get('longitude')
            
            # Note: with Supabase Python client, we can't easily send PostGIS 
            # ST_Point/ST_SetSRID without RPC, so we skip setting 'location' 
            # here unless we write a Postgres function. We just save lat/lon.
            
            if 'created_at' not in incident_data:
                incident_data['created_at'] = get_current_utc()
            if 'updated_at' not in incident_data:
                incident_data['updated_at'] = get_current_utc()
                
            response = self.client.table('incidents').upsert(incident_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create incident: {e}")
            return None

    def get_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('incidents').select('*').eq('id', incident_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch incident {incident_id}: {e}")
            return None

    def get_by_job(self, job_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('incidents').select('*').eq('ai_job_id', job_id).order('timestamp').execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch incidents for job {job_id}: {e}")
            return []

    def get_filtered(
        self,
        incident_type: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        min_confidence: Optional[float] = None,
        job_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        try:
            query = self.client.table('incidents').select('*')
            
            if incident_type:
                query = query.eq('incident_type', incident_type)
            if status:
                query = query.eq('status', status)
            if severity:
                query = query.eq('severity', severity)
            if min_confidence is not None:
                query = query.gte('confidence', min_confidence)
            if job_id:
                query = query.eq('ai_job_id', job_id)
                
            response = query.order('timestamp', desc=True).range(offset, offset + limit - 1).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to filter incidents: {e}")
            return []

    def count_filtered(
        self,
        incident_type: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        min_confidence: Optional[float] = None,
        job_id: Optional[str] = None
    ) -> int:
        try:
            query = self.client.table('incidents').select('id', count='exact')
            
            if incident_type:
                query = query.eq('incident_type', incident_type)
            if status:
                query = query.eq('status', status)
            if severity:
                query = query.eq('severity', severity)
            if min_confidence is not None:
                query = query.gte('confidence', min_confidence)
            if job_id:
                query = query.eq('ai_job_id', job_id)
                
            response = query.execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Failed to count filtered incidents: {e}")
            return 0

    def count(self) -> int:
        try:
            response = self.client.table('incidents').select('id', count='exact').execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Failed to count incidents: {e}")
            return 0

    def update_status(self, incident_id: str, new_status: str, metadata_updates: Optional[Dict[str, Any]] = None) -> bool:
        try:
            update_data = {
                "status": new_status,
                "updated_at": get_current_utc()
            }
            if metadata_updates:
                update_data["metadata"] = metadata_updates

            response = self.client.table('incidents').update(update_data).eq('id', incident_id).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to update incident status {incident_id}: {e}")
            return False


class TrafficWindowRepository:
    def __init__(self, client: Client):
        self.client = client

    def create(self, window_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if 'created_at' not in window_data:
                window_data['created_at'] = get_current_utc()
                
            response = self.client.table('traffic_windows').insert(window_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create traffic window: {e}")
            return None

    def get_latest(self, video_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            query = self.client.table('traffic_windows').select('*').order('created_at', desc=True)
            if video_id:
                query = query.eq('video_id', video_id)
            
            # Using limit 1 and executing
            response = query.limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch latest traffic window: {e}")
            return None

    def get_history(self, video_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            query = self.client.table('traffic_windows').select('*, ai_jobs(video_id)').order('created_at', desc=True)
            if video_id:
                # We can't filter by a joined table directly using .eq in standard postgrest without inner joins
                # but we'll fetch all and filter in memory if video_id is provided
                pass
            
            response = query.limit(limit).execute()
            
            results = []
            for r in response.data:
                v_id = r.get("ai_jobs", {}).get("video_id") if r.get("ai_jobs") else None
                if video_id and v_id != video_id:
                    continue
                r["video_id"] = v_id
                results.append(r)
                
            return results
        except Exception as e:
            logger.error(f"Failed to fetch traffic history: {e}")
            return []
            return []


class RoadSegmentRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_by_id(self, segment_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('road_segments').select('*').eq('id', segment_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch road segment {segment_id}: {e}")
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('road_segments').select('*').order('congestion_score', desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to list road segments: {e}")
            return []

    def update_scores(self, segment_id: str, pothole_count: int, incident_count: int, congestion_score: float) -> Optional[Dict[str, Any]]:
        try:
            update_data = {
                "pothole_count": pothole_count,
                "incident_count": incident_count,
                "congestion_score": congestion_score,
                "updated_at": get_current_utc()
            }
            response = self.client.table('road_segments').update(update_data).eq('id', segment_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update road segment {segment_id}: {e}")
            return None

    def create(self, segment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if 'created_at' not in segment_data:
                segment_data['created_at'] = get_current_utc()
            if 'updated_at' not in segment_data:
                segment_data['updated_at'] = get_current_utc()
                
            response = self.client.table('road_segments').insert(segment_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create road segment: {e}")
            return None


class BusRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_all(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('buses').select('*').execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch buses: {e}")
            return []

    def get_by_id(self, bus_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('buses').select('*').eq('id', bus_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to fetch bus {bus_id}: {e}")
            return None


class BusTelemetryRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_latest_for_bus(self, bus_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('bus_telemetry').select('*').eq('bus_id', bus_id).order('timestamp', desc=True).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to fetch telemetry for bus {bus_id}: {e}")
            return None

    def get_latest_all(self) -> List[Dict[str, Any]]:
        # Without a distinct on in supabase client easily, we can just fetch all and group in code if needed, 
        # or we just fetch recent ones. For now, fetch latest 100.
        try:
            response = self.client.table('bus_telemetry').select('*').order('timestamp', desc=True).limit(100).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch recent telemetry: {e}")
            return []


class MaintenanceRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_all(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('maintenance_tasks').select('*').order('created_at', desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch maintenance tasks: {e}")
            return []

    def create(self, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('maintenance_tasks').insert(task_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create maintenance task: {e}")
            return None
            
    def update_status(self, task_id: str, new_status: str, notes: Optional[str] = None) -> bool:
        try:
            update_data = {"status": new_status, "updated_at": get_current_utc()}
            if notes is not None:
                update_data["resolution_notes"] = notes
            if new_status == 'RESOLVED':
                update_data["resolved_at"] = get_current_utc()
            
            response = self.client.table('maintenance_tasks').update(update_data).eq('id', task_id).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to update maintenance task {task_id}: {e}")
            return False


class NotificationRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            response = self.client.table('notifications').select('*').order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch notifications: {e}")
            return []

    def mark_read(self, notification_id: str) -> bool:
        try:
            response = self.client.table('notifications').update({"read": True}).eq('id', notification_id).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to mark notification read {notification_id}: {e}")
            return False

class EvidenceRepository:
    def __init__(self, client: Client):
        self.client = client
        
    def create(self, evidence_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table('incident_evidence').insert(evidence_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create evidence: {e}")
            return None

