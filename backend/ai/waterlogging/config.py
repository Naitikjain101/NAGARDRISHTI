"""
Urban Watch — Waterlogging Detector Config
"""
import os
from pathlib import Path

def resolve_waterlogging_model() -> Path:
    # __file__ is backend/ai/waterlogging/config.py
    # parents[3] is the project root (where runs/ lives)
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "runs" / "segment" / "models" / "waterlogging" / "v2" / "weights" / "best.pt"

DEFAULT_WATERLOGGING_MODEL = str(resolve_waterlogging_model())
WATERLOGGING_IMGSZ = 640
WATERLOGGING_CONFIDENCE_THRESHOLD = 0.55   # Raised from 0.40 — V2 is a better-calibrated model
WATERLOGGING_IOU_THRESHOLD = 0.45

# Temporal validation tracking thresholds
WATERLOGGING_TRACKING_IOU_THRESHOLD = 0.30
WATERLOGGING_MIN_EVENT_FRAMES = 5
WATERLOGGING_FRAME_GAP_TOLERANCE = 10

# Geometry & severity thresholds
WATERLOGGING_MIN_AREA_RATIO = 0.02
WATERLOGGING_MAX_AREA_RATIO = 0.90

# ============================================================
# PHASE 10 — STEP 18 COMPLETE: V2 MODEL DEPLOYED
# V2 trained on 6 diverse video sources, proper video-level train/val/test split.
# Val metrics on genuinely unseen data:
#   Mask mAP50 = 72.8%   Mask mAP50-95 = 57.3%
#   Box  P=0.951  R=0.649
# SHA256: b8698dcd0683b8794a56a45cea56c2a66f76d322decccaee720da8c23b39922a
# WaterloggingValidator guards remain active (max_area_ratio=0.40, min_conf=0.55).
# ============================================================
WATERLOGGING_ENABLED = False
WATERLOGGING_TEST_MODE = True
