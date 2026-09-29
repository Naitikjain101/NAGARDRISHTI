import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger("urban_watch.db")

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

from typing import Optional

_supabase_client: Optional[Client] = None

def get_supabase() -> Client:
    """
    Returns the singleton Supabase client instance using the service_role key.
    This client bypasses RLS, so it must ONLY be used on the backend.
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
        
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "Supabase credentials not found. "
            "Please configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
        # We don't crash here so that the app can still start and show the "not configured" state
        # in the system status API, allowing graceful failures.
        class DummyClient:
            def __getattr__(self, name):
                raise RuntimeError("Supabase client is not configured")
        
        return DummyClient() # type: ignore
        
    try:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(f"Supabase client initialized for {SUPABASE_URL}")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        raise
