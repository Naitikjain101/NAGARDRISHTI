from db.supabase_client import get_supabase

client = get_supabase()
incidents = client.table("incidents").select("*").execute().data

for inc in incidents:
    inc_status = inc.get("status", "OPEN")
    
    # Map incident status to maintenance status
    action_status = "UNASSIGNED"
    if inc_status == "IN_PROGRESS":
        action_status = "IN_PROGRESS"
    elif inc_status == "RESOLVED":
        action_status = "RESOLVED"
    elif inc_status == "ASSIGNED":
        action_status = "ASSIGNED"
        
    client.table("maintenance_actions").update({"status": action_status}).eq("incident_id", inc["id"]).execute()
    print(f"Updated action for {inc['id']} to {action_status}")
