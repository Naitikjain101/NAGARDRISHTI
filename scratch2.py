from config import settings
from supabase import create_client
import sys

client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
demo_incidents = client.table("incidents").select("id").eq("metadata->>is_demo", "true").execute()
print(f"Found with eq: {len(demo_incidents.data)}")
