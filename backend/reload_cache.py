from db.supabase_client import get_supabase
client = get_supabase()
# PostgREST cache reload via SQL
client.rpc('reload_schema', {}).execute()
# If that RPC doesn't exist, just doing a generic query doesn't reload.
