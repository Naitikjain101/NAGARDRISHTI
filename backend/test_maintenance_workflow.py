import asyncio
from api.routes_actions import create_action, update_action, ActionUpdate
from db.supabase_client import get_supabase
import uuid

async def run_test():
    client = get_supabase()
    
    incident_id = str(uuid.uuid4())
    print(f"Creating mock incident {incident_id}")
    client.table("incidents").insert({
        "id": incident_id,
        "incident_type": "pothole",
        "severity": "HIGH",
        "status": "OPEN",
        "latitude": 0,
        "longitude": 0,
        "confidence": 0.9,
        "dedup_status": "CONFIRMED"
    }).execute()
    
    action = None
    try:
        action = await create_action(incident_id)
        print(f"Created action: {action['id']} with status {action['status']}")
        
        try:
            await create_action(incident_id)
            print("ERROR: Duplicate creation succeeded unexpectedly!")
        except Exception as e:
            print(f"Duplicate creation failed as expected: {type(e).__name__}")
            
        update1 = await update_action(action['id'], ActionUpdate(status="IN_PROGRESS"))
        print(f"Updated action to {update1['status']}")
        
        update2 = await update_action(action['id'], ActionUpdate(status="RESOLVED", resolution_note="Test fix"))
        print(f"Updated action to {update2['status']}")
        
        chk = client.table("incidents").select("status").eq("id", incident_id).execute()
        print(f"Incident final status: {chk.data[0].get('status')}")
        
    finally:
        print("Cleaning up mock incident and action")
        if action:
            client.table("maintenance_actions").delete().eq("id", action["id"]).execute()
        client.table("incidents").delete().eq("id", incident_id).execute()

asyncio.run(run_test())
