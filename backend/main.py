"""
Urban Watch — FastAPI Application Entry Point

Configures:
- CORS
- Static file serving (frontend)
- API routers
- Startup logging
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
import json
import time
from pathlib import Path
from typing import Callable

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import CORS_ORIGINS, UPLOAD_DIR, RESULTS_DIR, FRONTEND_DIR
from api.routes_video import router as video_router, set_directories as set_video_dirs
from api.routes_ai import router as ai_router, set_directories as set_ai_dirs
from api.routes_unified import router as unified_router, set_directories as set_unified_dirs
from api.events import router as events_router
from api.routes_incidents import router as incidents_router
from api.routes_traffic import router as traffic_router
from api.routes_system import router as system_router
from api.routes_annotation import router as annotation_router
from api.routes_maintenance import router as maintenance_router
from api.routes_fleet import router as fleet_router
from api.routes_notifications import router as notifications_router
from api.routes_waterlogging_forensic import router as waterlogging_forensic_router
from api.routes_pothole_lab import router as pothole_lab_router
from api.routes_missions import router as missions_router
from ai.common.device import get_device_info

# Configure Structured Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger("urban_watch")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Urban Watch API",
    description="AI-powered urban surveillance Command Center API",
    version="9.0.0",
)

# 1. Request ID Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    # Inject request_id into a context variable or just log it
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        f"Request {request.method} {request.url.path} completed in {process_time:.3f}s", 
        extra={"request_id": request_id}
    )
    
    response.headers["X-Request-ID"] = request_id
    return response

# 2. CORS
env_origin = os.environ.get("FRONTEND_ORIGIN")
origins = [env_origin] if env_origin else ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Standardized Error Handling
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", None)
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}", extra={"request_id": req_id})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "API_ERROR", "message": str(exc.detail), "request_id": req_id}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", None)
    logger.error(f"Unhandled exception: {exc}", exc_info=True, extra={"request_id": req_id})
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred.", "request_id": req_id}
    )

# Configure route directories
set_video_dirs(UPLOAD_DIR, RESULTS_DIR)
set_ai_dirs(UPLOAD_DIR, RESULTS_DIR)
set_unified_dirs(UPLOAD_DIR, RESULTS_DIR)

# Mount API routers
app.include_router(video_router)
app.include_router(ai_router)
app.include_router(unified_router)
app.include_router(events_router)
app.include_router(incidents_router) 
app.include_router(traffic_router)  
app.include_router(system_router)   
app.include_router(annotation_router, prefix="/api/waterlogging/annotations", tags=["annotation"])
app.include_router(maintenance_router)
app.include_router(fleet_router)
app.include_router(notifications_router)
app.include_router(waterlogging_forensic_router)
app.include_router(pothole_lab_router, prefix="/api")
app.include_router(missions_router)

@app.on_event("startup")
async def startup_event():
    """Initialize system, log device info, and cleanup stuck jobs."""
    import torch
    import ultralytics
    from db.supabase_client import get_supabase
    
    device_info = get_device_info()
    logger.info("Starting Urban Watch Backend Phase 9")
    logger.info("DEVICE: %s", device_info.device_str)
    
    # AI Job Reliability: Mark stuck processing jobs as FAILED
    try:
        client = get_supabase()
        client.table("ai_jobs").update({
            "status": "FAILED",
            "error": "Job aborted due to server restart"
        }).in_("status", ["QUEUED", "PROCESSING", "PENDING", "RUNNING"]).execute()
        logger.info("Cleaned up orphaned AI Jobs.")
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned jobs: {e}")

@app.get("/health")
async def health():
    """Production health check endpoint."""
    import torch
    import ultralytics
    from db.supabase_client import get_supabase
    device_info = get_device_info()
    
    db_status = "HEALTHY"
    try:
        client = get_supabase()
        client.table("buses").select("id").limit(1).execute()
    except Exception:
        db_status = "DEGRADED"

    return {
        "status": "HEALTHY" if db_status == "HEALTHY" else "DEGRADED",
        "database": db_status,
        "device": device_info.device_str,
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
    }

# Fallback serving (SPA routing is handled by nginx in production Docker, but useful for local)
_react_frontend = Path(__file__).parent.parent / "frontend-react" / "dist"
if _react_frontend.exists():
    app.mount("/app", StaticFiles(directory=str(_react_frontend), html=True), name="frontend_react")

