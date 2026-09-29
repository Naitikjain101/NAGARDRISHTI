import asyncio
from db.supabase import get_supabase
client = get_supabase()
res = client.table("incidents").select("id, metadata").execute()
for i in res.data:
    if "8dcec70e" in i["id"]:
        print("FOUND:", i)
