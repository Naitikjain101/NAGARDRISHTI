import logging
from typing import Optional, List, Dict, Any
from fastapi import Request, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.supabase_client import get_supabase
import os

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """
    Validates the Supabase JWT and retrieves the user profile.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")
        
    token = credentials.credentials
    client = get_supabase()

    try:
        # Validate token with Supabase Auth
        auth_response = client.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
            
        user = auth_response.user
        
        # Fetch the user profile and role
        profile_response = client.table("user_profiles").select("*").eq("user_id", user.id).execute()
        if not profile_response.data:
            # If no profile, we can fallback to VIEWER or raise error. 
            # Given the constraints, a profile is required.
            raise HTTPException(status_code=403, detail="User profile not found")
            
        profile = profile_response.data[0]
        
        if not profile.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is inactive")
            
        return {
            "id": user.id,
            "email": user.email,
            "profile_id": profile["id"],
            "username": profile["username"],
            "role": profile["role"],
            "display_name": profile.get("display_name")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def require_role(allowed_roles: List[str]):
    """
    Dependency generator for role-based access control.
    """
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

def require_admin(current_user: Dict[str, Any] = Depends(require_role(["ADMIN"]))):
    return current_user

def require_control_room(current_user: Dict[str, Any] = Depends(require_role(["ADMIN", "CONTROL_ROOM_OPERATOR"]))):
    return current_user

def require_maintenance(current_user: Dict[str, Any] = Depends(require_role(["ADMIN", "MAINTENANCE_OFFICER", "CONTROL_ROOM_OPERATOR"]))):
    return current_user

def require_authenticated(current_user: Dict[str, Any] = Depends(get_current_user)):
    return current_user
