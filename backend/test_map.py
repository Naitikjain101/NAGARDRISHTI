import asyncio
from db.supabase_client import get_supabase

async def test():
    client = get_supabase()
    q = client.table("incidents") \
        .select("id, incident_type, severity, status, confidence, latitude, longitude, "
                "observation_count, observed_by, dedup_status, first_seen_at, last_seen_at, "
                "created_at, metadata, maintenance_tasks(*)") \
        .not_.is_("latitude", "null") \
        .not_.is_("longitude", "null") \
        .gte("confidence", 0.0)
    
    resp = q.order("last_seen_at", desc=True).limit(500).execute()
    print("Incidents:", len(resp.data))
    
asyncio.run(test())
