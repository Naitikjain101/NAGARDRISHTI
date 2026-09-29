from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from db.supabase_client import get_supabase
from supabase import create_client
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class LoginRequest(BaseModel):
    identifier: str # Email or username
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict
    profile: dict

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticates a user via Supabase Auth.
    If the identifier does not contain an '@', it's treated as a username
    and resolved securely to an email using the backend's service role key.
    """
    client = get_supabase()
    email = req.identifier
    
    # Simple check for username vs email
    if "@" not in req.identifier:
        # Resolve username to email securely using service role
        response = client.table("user_profiles").select("user_id").eq("username", req.identifier).execute()
        if not response.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id = response.data[0]["user_id"]
        
        # We need the email for the user. We can use the admin API since we have service role key.
        try:
            admin_user_response = client.auth.admin.get_user_by_id(user_id)
            email = admin_user_response.user.email
        except Exception as e:
            logger.error(f"Failed to resolve username to email: {e}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    # Authenticate with Supabase using an ephemeral client to prevent polluting the backend singleton
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        # Use anon key or fallback to service key; creating a new client isolates the auth session
        supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        auth_client = create_client(supabase_url, supabase_key)
        
        auth_response = auth_client.auth.sign_in_with_password({
            "email": email,
            "password": req.password
        })
        
        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        # Fetch profile to include in response (using service role client)
        profile_response = client.table("user_profiles").select("*").eq("user_id", auth_response.user.id).execute()
        profile_data = profile_response.data[0] if profile_response.data else {}
        
        if not profile_data.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is inactive")
            
        return LoginResponse(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            user={"id": auth_response.user.id, "email": auth_response.user.email},
            profile=profile_data
        )
    except Exception as e:
        logger.error(f"Login failed: {e}")
        # Return generic error to avoid user enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")
