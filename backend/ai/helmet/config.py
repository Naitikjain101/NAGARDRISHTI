"""
Urban Watch — Helmet Detection Configuration

Model: best_roadx.pt
Classes: helmet, licenseplate, motorcyclist, nohelmet

IMPORTANT:
- best_roadx.pt was NOT FOUND on disk during Phase 5 architecture audit.
- This configuration is prepared for when the model file is available.
- If the model file is absent, HelmetDetector gracefully disables detection.
- Do NOT replace best_roadx.pt with any other model without evidence.

Application mapping (Phase 5L specification):
- helmet      → user-facing: HELMET event
- nohelmet    → user-facing: NO_HELMET event
- licenseplate → DISABLED from user-facing UI
- motorcyclist → INTERNAL tracking only (not user-facing events)

Python 3.9 compatible.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Model path — configurable via environment variable or direct assignment
# ---------------------------------------------------------------------------

# Default expected location for the helmet model
_HELMET_WEIGHTS_DIR = Path(__file__).parent / "weights"
_DEFAULT_HELMET_MODEL = _HELMET_WEIGHTS_DIR / "best_roadx.pt"

# Allow override via environment variable
HELMET_MODEL_PATH: str = os.environ.get(
    "URBAN_WATCH_HELMET_MODEL",
    str(_DEFAULT_HELMET_MODEL),
)

# ---------------------------------------------------------------------------
# Inference settings
# ---------------------------------------------------------------------------

HELMET_IMGSZ: int = 640
HELMET_CONFIDENCE_THRESHOLD: float = 0.40  # Higher threshold for safety events
HELMET_IOU_THRESHOLD: float = 0.45

# Temporal confirmation settings
HELMET_MIN_CONFIRMATION_FRAMES: int = 2  # Require 2+ frames before reporting
HELMET_FRAME_GAP_TOLERANCE: int = 3

# ---------------------------------------------------------------------------
# Class mapping
# ---------------------------------------------------------------------------

# Canonical class names from best_roadx.pt
HELMET_CLASS_NAMES = {
    "helmet",
    "nohelmet",
    "licenseplate",  # DO NOT expose in UI
    "motorcyclist",  # Internal only
}

# Classes that generate user-facing incidents
HELMET_USER_FACING_CLASSES = {"helmet", "nohelmet"}

# Application-level name mapping
HELMET_CLASS_MAPPING = {
    "helmet": "helmet",       # maps to IncidentType.HELMET
    "nohelmet": "no_helmet",  # maps to IncidentType.NO_HELMET
}

# Classes that are suppressed from user-facing output
HELMET_SUPPRESSED_CLASSES = {"licenseplate"}

# Classes used for internal context only
HELMET_INTERNAL_CLASSES = {"motorcyclist"}
