import sys
import os
import asyncio
from itertools import combinations
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from db.supabase_client import get_supabase
from ai.gis.interpolator import haversine_distance_m

client = get_supabase()

# Fetch all open pothole and waterlogging incidents
resp = client.table("incidents").select("id, incident_type, latitude, longitude, observation_count, observed_by, created_at, status").in_("incident_type", ["pothole", "waterlogging"]).not_.is_("latitude", "null").execute()
incidents = resp.data or []

print(f"Total incidents to analyze: {len(incidents)}")

duplicates = 0
unique_clusters = []

for inc in incidents:
    lat, lng = inc.get("latitude"), inc.get("longitude")
    itype = inc.get("incident_type")
    
    radius = 25.0 if itype == "pothole" else 50.0
    
    merged = False
    for cluster in unique_clusters:
        if cluster["type"] == itype:
            clat, clng = cluster["lat"], cluster["lng"]
            if haversine_distance_m(lat, lng, clat, clng) <= radius:
                cluster["count"] += 1
                cluster["ids"].append(inc["id"])
                merged = True
                break
    if not merged:
        unique_clusters.append({
            "type": itype,
            "lat": lat,
            "lng": lng,
            "count": 1,
            "ids": [inc["id"]]
        })

print(f"Unique physical incidents: {len(unique_clusters)}")
duplicates_to_delete = sum(c["count"] - 1 for c in unique_clusters)
print(f"Duplicates to merge/delete: {duplicates_to_delete}")
