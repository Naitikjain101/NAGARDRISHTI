from db.supabase_client import get_supabase
client = get_supabase()
try:
    signed = client.storage.from_("urban_watch_evidence").create_signed_url("uploads/4d174fc9-82a7-4afe-a32e-62a7e56de8d7.mp4", 3600)
    print("Signed:", signed)
except Exception as e:
    import traceback
    traceback.print_exc()
