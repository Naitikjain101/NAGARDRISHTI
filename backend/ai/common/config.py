"""
Urban Watch — AI Common Configuration

All configurable AI thresholds live here.
Do NOT bury thresholds inside detection or tracking logic.
Python 3.9 compatible: uses Optional[str] instead of str | None.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

# Pretrained model candidates in priority order.
# Each entry is a dict with the Ultralytics model name and metadata.
MODEL_CANDIDATES = [
    {
        "name": "yolo26n",
        "pt_file": "yolo26n.pt",
        "family": "YOLO26",
        "priority": 1,
        "description": "Latest Ultralytics family — NMS-free, edge-optimized",
    },
    {
        "name": "yolo26s",
        "pt_file": "yolo26s.pt",
        "family": "YOLO26",
        "priority": 2,
        "description": "YOLO26 small — higher accuracy than nano",
    },
    {
        "name": "yolo11n",
        "pt_file": "yolo11n.pt",
        "family": "YOLO11",
        "priority": 3,
        "description": "YOLO11 nano — mature, stable, well-benchmarked",
    },
    {
        "name": "yolo11s",
        "pt_file": "yolo11s.pt",
        "family": "YOLO11",
        "priority": 4,
        "description": "YOLO11 small — larger than nano, better accuracy",
    },
    {
        "name": "yolo12n",
        "pt_file": "yolo12n.pt",
        "family": "YOLO12",
        "priority": 5,
        "description": "YOLO12 nano — attention-centric, research-grade",
    },
]

# The model selected for production inference after benchmarking.
# Selected as provisional production vehicle detector based on visual forensic benchmark.
PRODUCTION_MODEL: str = "yolov8n.pt"

# ---------------------------------------------------------------------------
# Inference configuration
# ---------------------------------------------------------------------------

# Inference image size (pixels, square).
INFERENCE_IMGSZ: int = 640

# Confidence threshold for detections.
CONFIDENCE_THRESHOLD: float = 0.30

# IOU threshold for NMS (Non-Maximum Suppression).
IOU_THRESHOLD: float = 0.45

# ---------------------------------------------------------------------------
# Vehicle Smart Duplicate Suppression & Temporal Stabilization
# ---------------------------------------------------------------------------

# Same-class duplicate suppression threshold (IoU >= 0.75 -> keep higher conf)
VEHICLE_SAME_CLASS_IOU: float = 0.75

# Confusable cross-class duplicate suppression thresholds
VEHICLE_CROSS_CLASS_IOU: float = 0.65
VEHICLE_CROSS_CLASS_IOMIN: float = 0.80

# Confusable class pairs subject to cross-class duplicate suppression
CONFUSABLE_CROSS_CLASS_PAIRS = [
    ("car", "truck"),
    ("bus", "truck"),
    ("motorcycle", "bicycle"),
]

# Rolling class history window size for temporal stabilization
VEHICLE_CLASS_HISTORY_SIZE: int = 10

# Frame sampling interval.
# 1 = every frame (baseline, use until accuracy baseline is established).
# 2 = every other frame.
# 3 = every third frame.
FRAME_INTERVAL: int = 1

# Batch size for inference.
# Benchmarked values: 1, 2, 4.
# Default 1 — MPS has limited benefit from batching on detection tasks.
BATCH_SIZE: int = 1

# ---------------------------------------------------------------------------
# Traffic density configuration
# ---------------------------------------------------------------------------

# Rolling window size in seconds for density calculation.
DENSITY_WINDOW_SECONDS: float = 5.0

# Configurable density thresholds.
# These are prototype thresholds — NOT calibrated traffic engineering values.
# Documented as prototype in density.py and PHASE_1_REPORT.md.
TRAFFIC_LOW_THRESHOLD: int = 5        # < 5 unique vehicles → LOW
TRAFFIC_MEDIUM_THRESHOLD: int = 15    # 5–14 → MEDIUM, ≥15 → HIGH

# ---------------------------------------------------------------------------
# Tracking configuration
# ---------------------------------------------------------------------------

# ByteTrack configuration file — Ultralytics built-in.
# If None, uses default ByteTrack settings.
BYTETRACK_CONFIG: Optional[str] = None

# Minimum track length (frames) before a track is considered confirmed.
MIN_TRACK_FRAMES: int = 3

# ---------------------------------------------------------------------------
# Confidence sweep values for benchmarking
# ---------------------------------------------------------------------------
CONFIDENCE_SWEEP = [0.20, 0.25, 0.30, 0.40, 0.50]

# ---------------------------------------------------------------------------
# Image size sweep values for benchmarking
# ---------------------------------------------------------------------------
IMGSZ_SWEEP = [320, 416, 512, 640]

# ---------------------------------------------------------------------------
# Batch size sweep values for benchmarking
# ---------------------------------------------------------------------------
BATCH_SWEEP = [1, 2, 4]

# ---------------------------------------------------------------------------
# Frame interval sweep values for benchmarking
# ---------------------------------------------------------------------------
INTERVAL_SWEEP = [1, 2, 3]

# ---------------------------------------------------------------------------
# Phase 5: Advanced AI Filtering & Intelligence
# ---------------------------------------------------------------------------

# 1. Road ROI Configuration
# By default we mask out the top 35% of the frame (sky/distant horizon).
ROAD_ROI_POLYGON = [
    [0.0, 0.35], 
    [1.0, 0.35], 
    [1.0, 1.0], 
    [0.0, 1.0]
]

# 2. Geometric Filters
# Min/Max bounding box area as a percentage of the total frame area
POTHOLE_MIN_AREA_RATIO: float = 0.0005  # extremely small noise
POTHOLE_MAX_AREA_RATIO: float = 0.30    # unlikely to be 30% of entire frame

# Aspect Ratio (width / height)
# Very long horizontal lines or extremely tall vertical strips are likely artifacts
POTHOLE_MIN_ASPECT_RATIO: float = 0.2
POTHOLE_MAX_ASPECT_RATIO: float = 5.0

# Minimum percentage of the pothole bounding box that must fall inside the ROI
POTHOLE_MIN_ROI_OVERLAP: float = 0.50

# 3. Vehicle Interaction Suppression
# How much of the pothole box must be covered by a vehicle box to trigger suppression
INTERSECTION_OVER_POTHOLE_AREA: float = 0.50
# How much of the vehicle box is covered by the pothole (helps filter out huge vehicle boxes catching small potholes by chance)
INTERSECTION_OVER_VEHICLE_AREA: float = 0.01

# Classes that aggressively trigger suppression
SUPPRESSING_VEHICLE_CLASSES = ["car", "bus", "truck", "motorcycle"]

# 4. Severity Thresholds
# Estimated Severity Area Thresholds (fraction of frame area). NOT physical depth.
POTHOLE_SEVERITY_THRESHOLDS = {
    "LOW_AREA": 0.02,     # < 2% of frame
    "MEDIUM_AREA": 0.05,  # 2% - 5% of frame
    "HIGH_AREA": 0.10,    # 5% - 10% of frame
                          # > 10% is CRITICAL
}

POTHOLE_SEVERITY_COLORS = {
    "LOW": "Yellow",
    "MEDIUM": "Orange",
    "HIGH": "Red",
    "CRITICAL": "Purple",
}

# ---------------------------------------------------------------------------
# Phase 5C: PotholeValidator — Multi-Signal Composite Scoring
# ---------------------------------------------------------------------------
# Each weight represents the contribution of that signal to the composite
# incident confidence score. All weights should sum to 1.0.
# These are INITIAL values based on engineering intuition — NOT empirically
# calibrated. Run ablation benchmarks before changing in production.

# Weight: raw model confidence (primary signal)
POTHOLE_WEIGHT_MODEL_CONFIDENCE: float = 0.35

# Weight: temporal persistence (more frames = more real)
POTHOLE_WEIGHT_TEMPORAL: float = 0.25

# Weight: spatial stability (low position variance = more real)
POTHOLE_WEIGHT_SPATIAL: float = 0.20

# Weight: geometry reasonableness (appropriate bbox size)
POTHOLE_WEIGHT_GEOMETRY: float = 0.10

# Weight: detection frequency (how dense relative to span)
POTHOLE_WEIGHT_FREQUENCY: float = 0.10

# Penalty: deducted from score if bbox overlaps with vehicle
POTHOLE_VEHICLE_OVERLAP_PENALTY: float = 0.30

# Minimum span_frames to grant temporal credit
POTHOLE_MIN_TEMPORAL_FRAMES: int = 3

# Minimum composite score to accept as a confirmed incident
# Events scoring below this threshold are flagged as low-confidence
POTHOLE_MIN_INCIDENT_SCORE: float = 0.35

# Spatial deduplication: max bbox center distance (normalized 0-1)
# Events with centers closer than this are merged into one incident
POTHOLE_DEDUP_CENTER_DISTANCE: float = 0.08

# ---------------------------------------------------------------------------
# Phase 5E: CongestionEngine Configuration
# ---------------------------------------------------------------------------

# SEVERE threshold: unique vehicles >= this per window
TRAFFIC_SEVERE_THRESHOLD: int = 30

# Congestion score weights (normalized [0, 1] output)
# Score = unique_vehicle_count / congestion_reference_density
CONGESTION_REFERENCE_DENSITY: int = 50  # 50 unique vehicles/window = max score

# ---------------------------------------------------------------------------
# Phase 5H: Road Risk Score Weights
# ---------------------------------------------------------------------------
# These produce the road segment risk score.
# NOT scientifically validated — advisory operational indicator only.

ROAD_RISK_POTHOLE_WEIGHT: float = 0.50
ROAD_RISK_CONGESTION_WEIGHT: float = 0.25
ROAD_RISK_SAFETY_WEIGHT: float = 0.25

# Reference values for normalization
ROAD_RISK_MAX_POTHOLES: int = 10
ROAD_RISK_MAX_VIOLATIONS: int = 5
