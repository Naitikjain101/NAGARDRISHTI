import os
import sys
import logging
from pathlib import Path

# Add backend directory to Python path so we can import db.supabase_client
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.supabase_client import get_supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "username": "demo.admin",
        "email": "demo.admin@nagar-drishti.demo",
        "password": "NagarDrishti@Demo2026!",
        "role": "ADMIN",
        "display_name": "Demo Administrator"
    },
    {
        "username": "demo.operator",
        "email": "demo.operator@nagar-drishti.demo",
        "password": "NagarDrishti@Demo2026!",
        "role": "CONTROL_ROOM_OPERATOR",
        "display_name": "Demo Control Room Operator"
    },
    {
        "username": "demo.maintenance",
        "email": "demo.maintenance@nagar-drishti.demo",
        "password": "NagarDrishti@Demo2026!",
        "role": "MAINTENANCE_OFFICER",
        "display_name": "Demo Maintenance Officer"
    },
    {
        "username": "demo.viewer",
        "email": "demo.viewer@nagar-drishti.demo",
        "password": "NagarDrishti@Demo2026!",
        "role": "VIEWER",
        "display_name": "Demo Viewer"
    }
]

def create_demo_users():
    """
    Creates demo users in Supabase Auth and inserts their roles into public.user_profiles.
    Idempotent operation using the service role key.
    """
    for user_data in DEMO_USERS:
        client = get_supabase() # get fresh client
        email = user_data["email"]
        username = user_data["username"]
        role = user_data["role"]
        display_name = user_data["display_name"]
        password = user_data["password"]
        
        logger.info(f"Processing demo user: {username}")
        
        # 1. Create or get user in Supabase Auth
        # Note: supabase-py doesn't have a direct "get user by email" admin method exposed cleanly,
        # but admin.create_user will fail if the user exists. We can catch that or list users.
        user_id = None
        try:
            # Try to create user
            response = client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })
            user_id = response.user.id
            logger.info(f"Created new Auth user for {email} with ID: {user_id}")
        except Exception as e:
            if "already exists" in str(e).lower() or "already been registered" in str(e).lower():
                logger.info(f"Auth user for {email} already exists. Fetching ID...")
                try:
                    # Create a separate client for sign in so we don't pollute the admin client
                    import os
                    from supabase import create_client
                    supabase_url = os.getenv("SUPABASE_URL")
                    supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                    auth_client = create_client(supabase_url, supabase_key)
                    auth_resp = auth_client.auth.sign_in_with_password({"email": email, "password": password})
                    user_id = auth_resp.user.id
                    logger.info(f"Found existing user ID: {user_id}")
                except Exception as inner_e:
                    logger.error(f"Failed to authenticate existing user {email} to retrieve ID: {inner_e}")
                    continue
            else:
                logger.error(f"Failed to create Auth user {email}: {e}")
                continue
                
        if not user_id:
            logger.error(f"Could not resolve user_id for {email}")
            continue
            
        # 2. Upsert profile in public.user_profiles
        try:
            # Check if profile exists
            profile_resp = client.table("user_profiles").select("id").eq("user_id", user_id).execute()
            
            profile_payload = {
                "user_id": user_id,
                "username": username,
                "role": role,
                "display_name": display_name,
                "is_active": True
            }
            
            if profile_resp.data:
                # Update existing profile
                client.table("user_profiles").update(profile_payload).eq("user_id", user_id).execute()
                logger.info(f"Updated profile for {username}")
            else:
                # Insert new profile
                client.table("user_profiles").insert(profile_payload).execute()
                logger.info(f"Created profile for {username}")
        except Exception as e:
            logger.error(f"Failed to upsert profile for {username}: {e}")

if __name__ == "__main__":
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        logger.warning("SUPABASE_SERVICE_ROLE_KEY is missing. Demo users cannot be provisioned.")
    else:
        create_demo_users()
        logger.info("Demo user provisioning complete.")
