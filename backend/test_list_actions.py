import asyncio
from db.supabase_client import get_supabase

async def test():
    client = get_supabase()
    actions_resp = client.table('maintenance_actions').select('*').execute()
    actions = actions_resp.data
    print("Actions:", len(actions))
    
    incident_ids = [a['incident_id'] for a in actions if a.get('incident_id')]
    incidents = []
    if incident_ids:
        inc_resp = client.table('incidents').select('*').in_('id', incident_ids).execute()
        incidents = inc_resp.data
    print("Incidents:", len(incidents))

asyncio.run(test())
