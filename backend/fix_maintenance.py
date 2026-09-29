from db.supabase_client import get_supabase
from api.routes_actions import get_action_type_for_incident

client = get_supabase()
incidents = client.table("incidents").select("*").execute().data

for inc in incidents:
    action_data = {
        "incident_id": inc["id"],
        "status": "UNASSIGNED",
        "action_type": get_action_type_for_incident(inc.get("incident_type", ""))
    }
    client.table("maintenance_actions").upsert(action_data, on_conflict="incident_id").execute()
    print(f"Created action for {inc['id']}")
