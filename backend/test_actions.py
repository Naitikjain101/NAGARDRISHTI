from db.supabase_client import get_supabase
client = get_supabase()
try:
    actions_resp = client.table('maintenance_actions').select('*').execute()
    actions = actions_resp.data
    if actions:
        incident_ids = [a['incident_id'] for a in actions if a.get('incident_id')]
        if incident_ids:
            inc_resp = client.table('incidents').select('*').in_('id', incident_ids).execute()
            print("incidents length:", len(inc_resp.data))
    print("actions length:", len(actions))
except Exception as e:
    import traceback
    traceback.print_exc()
