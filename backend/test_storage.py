from db.supabase_client import get_supabase
client = get_supabase()
try:
    print(client.storage.from_("urban_watch_evidence").list("uploads", {"search": "4d174fc9-82a7-4afe-a32e-62a7e56de8d7"}))
except Exception as e:
    print("Dict error:", e)

try:
    from storage3.utils import SearchOptions
    print(client.storage.from_("urban_watch_evidence").list("uploads", SearchOptions(search="4d174fc9-82a7-4afe-a32e-62a7e56de8d7")))
except Exception as e:
    print("SearchOptions error:", e)
