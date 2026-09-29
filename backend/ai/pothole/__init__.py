"""
Urban Watch — Pothole Detection & Tracking Package (Phase 2)
"""

from ai.pothole.config import (
    DEFAULT_POTHOLE_MODEL,
    POTHOLE_CONFIDENCE_THRESHOLD,
    POTHOLE_IMGSZ,
    POTHOLE_IOU_THRESHOLD,
)
from ai.pothole.detector import PotholeDetector, PotholeDetectorConfig
from ai.pothole.model_inspector import inspect_pothole_model
from ai.pothole.model_registry import PotholeModelRegistry, pothole_registry
from ai.pothole.schemas import (
    PotholeDetection,
    PotholeEvent,
    PotholeFrameResult,
    PotholeVideoSummary,
)
from ai.pothole.tracker import PotholeEventTracker

__all__ = [
    "PotholeDetector",
    "PotholeDetectorConfig",
    "PotholeDetection",
    "PotholeEvent",
    "PotholeFrameResult",
    "PotholeVideoSummary",
    "PotholeEventTracker",
    "inspect_pothole_model",
    "PotholeModelRegistry",
    "pothole_registry",
    "DEFAULT_POTHOLE_MODEL",
    "POTHOLE_IMGSZ",
    "POTHOLE_CONFIDENCE_THRESHOLD",
    "POTHOLE_IOU_THRESHOLD",
]
