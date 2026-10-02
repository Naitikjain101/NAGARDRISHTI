"""
Urban Watch — Server Configuration

Top-level server settings (separate from AI configuration).
AI thresholds live in backend/ai/common/config.py.
"""

from __future__ import annotations

import os
from pathlib import Path

# Base directory (this file's directory)
BASE_DIR = Path(__file__).parent

# Upload directory for received videos
UPLOAD_DIR = BASE_DIR / "uploads"

# Results directory for AI JSON outputs
RESULTS_DIR = BASE_DIR / "results"

# Frontend static files directory
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# CORS origins allowed
CORS_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  # for dev servers
    "http://127.0.0.1:3000",
    "http://localhost:5500",  # python http.server
    "http://127.0.0.1:5500",
    "https://nagardrishti-nine.vercel.app", # Vercel Production
    "https://nagardrishti-hd.vercel.app",
]

# Maximum upload file size (bytes) — 500 MB
MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
