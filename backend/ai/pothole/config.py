"""
Urban Watch — Pothole Detection Configuration

Empirically derived from Phase 2 Step 2 Benchmarking:
- Model: YOLO26n (trained at 640px)
- Resolution: 640 (optimal accuracy/speed tradeoff: mAP50=0.9401, mAP50-95=0.8103, 17.3ms latency)
- Confidence: 0.25 (optimal F1=0.9265, 100% recall on validation instances)
- NMS IoU: 0.45 (eliminates intra-frame anchor duplicates)
- Min Event Frames: 3 (filters out single-frame transient noise)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Base directory for weights
POTHOLE_DIR = Path(__file__).parent
WEIGHTS_DIR = POTHOLE_DIR / "weights"

# Default Model Checkpoint
DEFAULT_POTHOLE_MODEL = str(WEIGHTS_DIR / "yolo26m_pothole_best.pt")

# Inference Settings (Benchmark Proven)
POTHOLE_IMGSZ: int = 640
POTHOLE_CONFIDENCE_THRESHOLD: float = 0.65
POTHOLE_IOU_THRESHOLD: float = 0.45

# Video Event Tracking Settings
POTHOLE_MIN_EVENT_FRAMES: int = 15
POTHOLE_FRAME_GAP_TOLERANCE: int = 5
POTHOLE_TRACKING_IOU_THRESHOLD: float = 0.20

# Available / Audited Model Variants
AUDITED_MODELS = {
    "yolo26m_pothole_best": {
        "path": str(WEIGHTS_DIR / "yolo26m_pothole_best.pt"),
        "family": "YOLO26m",
        "native_imgsz": 640,
        "classes": {0: "pothole"},
        "status": "APPROVED_PRODUCTION",
        "notes": "New YOLO26m production model. Replaces yolov8m_peterhdd."
    },
    "yolov8m_peterhdd": {
        "path": str(WEIGHTS_DIR / "pothole_yolov8_peterhdd.pt"),
        "family": "YOLOv8m",
        "native_imgsz": 640,
        "classes": {0: "pothole"},
        "status": "DEPRECATED_BACKUP",
        "notes": "Hugging Face model. Massive reduction in false positives on complex road textures vs yolo26n."
    },
    "yolo26n_640": {
        "path": str(WEIGHTS_DIR / "pothole_yolo26n_640.pt"),
        "family": "YOLO26n",
        "native_imgsz": 640,
        "classes": {0: "pothole"},
        "status": "DEPRECATED_NOISY",
        "notes": "Native 640px training. Extremely noisy on empty roads with complex textures (1700+ raw detections)."
    },
    "yolov8n_256": {
        "path": str(WEIGHTS_DIR / "pothole_yolov8n_256.pt"),
        "family": "YOLOv8n",
        "native_imgsz": 256,
        "classes": {0: "pothole"},
        "status": "DEPRECATED_INFERIOR",
        "notes": "Native 256px training. Severe resolution mismatch when run at 640px."
    }
}
