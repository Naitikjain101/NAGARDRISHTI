from db.supabase_client import get_supabase

client = get_supabase()
try:
    q = client.table("incidents") \
        .select("id, incident_type, severity, status, confidence, latitude, longitude, "
                "observation_count, observed_by, dedup_status, first_seen_at, last_seen_at, "
                "created_at, metadata, maintenance_tasks(*)") \
        .not_.is_("latitude", "null") \
        .not_.is_("longitude", "null") \
        .gte("confidence", 0.0)
    
    resp = q.order("last_seen_at", desc=True).limit(10).execute()
    print("Success:", len(resp.data))
except Exception as e:
    import traceback
    traceback.print_exc()
