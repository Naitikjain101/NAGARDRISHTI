import sys
import os
import asyncio
from datetime import datetime, timezone
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from db.supabase_client import get_supabase
from ai.gis.interpolator import haversine_distance_m

def run_migration():
    client = get_supabase()

    print("Fetching incidents...")
    resp = client.table("incidents").select("*").in_("incident_type", ["pothole", "waterlogging"]).not_.is_("latitude", "null").order("first_seen_at", desc=False).execute()
    incidents = resp.data or []

    print(f"Total incidents to analyze: {len(incidents)}")

    unique_clusters = []
    duplicates_to_process = []

    for inc in incidents:
        lat, lng = inc.get("latitude"), inc.get("longitude")
        itype = inc.get("incident_type")
        
        radius = 25.0 if itype == "pothole" else 50.0
        
        merged = False
        for cluster in unique_clusters:
            if cluster["type"] == itype:
                clat, clng = cluster["canonical_incident"]["latitude"], cluster["canonical_incident"]["longitude"]
                if haversine_distance_m(lat, lng, clat, clng) <= radius:
                    cluster["duplicates"].append(inc)
                    merged = True
                    break
        
        if not merged:
            unique_clusters.append({
                "type": itype,
                "canonical_incident": inc,
                "duplicates": []
            })

    print(f"Unique physical incidents: {len(unique_clusters)}")
    
    for cluster in unique_clusters:
        if not cluster["duplicates"]:
            continue
            
        canonical = cluster["canonical_incident"]
        canonical_id = canonical["id"]
        
        print(f"\nMerging {len(cluster['duplicates'])} duplicates into canonical incident {canonical_id}...")
        
        # Merge properties
        all_incidents = [canonical] + cluster["duplicates"]
        
        # 1. Merge observed_by
        observed_by_set = set()
        for inc in all_incidents:
            obs = inc.get("observed_by") or []
            observed_by_set.update(obs)
            
        # 2. Update observation_count
        new_obs_count = sum(inc.get("observation_count") or 1 for inc in all_incidents)
        
        # 3. dedup_status
        new_dedup = "CONFIRMED" if new_obs_count >= 3 else "PENDING"
        
        # 4. confidence
        max_conf = max((inc.get("confidence") or 0.0) for inc in all_incidents)
        
        # Update canonical incident in DB
        client.table("incidents").update({
            "observed_by": list(observed_by_set),
            "observation_count": new_obs_count,
            "dedup_status": new_dedup,
            "confidence": max_conf,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", canonical_id).execute()
        
        for dup in cluster["duplicates"]:
            dup_id = dup["id"]
            print(f"  Reassigning observations and evidence from {dup_id} to {canonical_id}")
            
            # Reassign observations
            client.table("incident_observations").update({
                "incident_id": canonical_id
            }).eq("incident_id", dup_id).execute()
            
            # Reassign evidence
            client.table("incident_evidence").update({
                "incident_id": canonical_id
            }).eq("incident_id", dup_id).execute()
            
            # Reassign maintenance tasks
            client.table("maintenance_tasks").update({
                "incident_id": canonical_id
            }).eq("incident_id", dup_id).execute()
            
            # Delete duplicate incident
            client.table("incidents").delete().eq("id", dup_id).execute()
            print(f"  Deleted duplicate {dup_id}")

    print("\nMigration complete.")

if __name__ == "__main__":
    run_migration()
