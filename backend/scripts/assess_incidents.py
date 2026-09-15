import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db.supabase_client import get_supabase

client = get_supabase()

def assess_incidents():
    print("Fetching incidents...")
    res = client.table("incidents").select("id, status, latitude, longitude, source_mission_id, ai_job_id").execute()
    incidents = res.data
    
    total = len(incidents)
    no_gps = len([i for i in incidents if i.get("latitude") is None or i.get("longitude") is None])
    with_mission = len([i for i in incidents if i.get("source_mission_id") is not None])
    with_job_only = len([i for i in incidents if i.get("source_mission_id") is None and i.get("ai_job_id") is not None])
    
    no_gps_with_mission = len([i for i in incidents if (i.get("latitude") is None or i.get("longitude") is None) and i.get("source_mission_id") is not None])
    no_gps_standalone = len([i for i in incidents if (i.get("latitude") is None or i.get("longitude") is None) and i.get("source_mission_id") is None])
    
    print(f"Total incidents: {total}")
    print(f"Incidents missing GPS: {no_gps}")
    print(f"  - Missing GPS but HAS source_mission_id (propagation bug): {no_gps_with_mission}")
    print(f"  - Missing GPS and NO source_mission_id (standalone upload): {no_gps_standalone}")
    
    print("\nFetching incident_observations...")
    obs_res = client.table("incident_observations").select("id, incident_id, bbox, video_timestamp, latitude").execute()
    observations = obs_res.data
    
    obs_total = len(observations)
    obs_no_bbox = len([o for o in observations if o.get("bbox") is None])
    
    print(f"Total observations: {obs_total}")
    print(f"Observations missing geometry (bbox): {obs_no_bbox}")
    
    inc_ids_with_obs = set(o["incident_id"] for o in observations if o.get("incident_id"))
    incs_no_obs = total - len(inc_ids_with_obs)
    
    print(f"Incidents with 0 observations: {incs_no_obs}")

if __name__ == "__main__":
    assess_incidents()
