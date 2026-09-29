"""
Urban Watch — Safe Model Registry
Phase 19: Universal AI Model Lab

RULES:
- Every registered model must physically exist on disk.
- Models that are absent (e.g. best_roadx.pt) are status=UNAVAILABLE.
- SHA256 is verified on first load and cached — never re-hashed per frame.
- Frontend sends model_id; backend resolves to trusted path from this registry.
- DO NOT delete or rename model files without updating sha256 here.
"""
from __future__ import annotations

import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------
# This file lives at:  backend/ai/models/registry.py
_REGISTRY_DIR = Path(__file__).resolve().parent          # backend/ai/models/
MODELS_DIR    = _REGISTRY_DIR.parent                     # backend/ai/
BACKEND_DIR   = MODELS_DIR.parent                        # backend/
PROJECT_ROOT  = BACKEND_DIR.parent                       # project root

CONFIG_PATH   = _REGISTRY_DIR / "active_config.json"
PREVIOUS_CONFIG_PATH = _REGISTRY_DIR / "previous_config.json"

# ---------------------------------------------------------------------------
# SHA256 cache — populated on first load, reused thereafter
# ---------------------------------------------------------------------------
_sha256_cache: Dict[str, str] = {}

def _calculate_sha256(filepath: str) -> str:
    """Compute SHA256 of a file. Returns '' if file not found."""
    if filepath in _sha256_cache:
        return _sha256_cache[filepath]
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        result = h.hexdigest()
        _sha256_cache[filepath] = result
        return result
    except FileNotFoundError:
        return ""

# ---------------------------------------------------------------------------
# Authoritative Model Registry
#
# All physical .pt files found during Phase 19 audit are listed here.
# Models not found on disk have status=UNAVAILABLE.
#
# Pothole SHA256 verified 2026-09-14:
#   yolo26m_pothole_best.pt       → 8e5da7c4c2f9f933f581c3ad8d4c69d23aa2dbd19030b6bf40ac21fdce6f5be1
#   pothole_yolov8_peterhdd.pt    → af2ac6ce7bfec72e71643659ac946caf80ced84869e526a60135c457abfbb200
# Waterlogging SHA256 verified 2026-09-14:
#   waterlogging/v1/best.pt       → a2a1b13cc42f4f86ba4ec0f0bdfc524065bce5291eb3e698c56d3cdcdb968694
#   waterlogging/v2/best.pt       → b8698dcd0683b8794a56a45cea56c2a66f76d322decccaee720da8c23b39922a
# Object SHA256 verified 2026-09-14:
#   yolov8n.pt                    → f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36
# ---------------------------------------------------------------------------
REGISTERED_MODELS: Dict[str, Dict[str, Any]] = {

    # ================================================================
    # POTHOLE — bounding-box detection
    # ================================================================
    "POTHOLE": {
        "yolo26m_pothole_best": {
            "display_name": "YOLO26m Pothole (Production)",
            "task": "POTHOLE",
            "architecture": "YOLO26m",
            "version": "1.0",
            "model_path": str(MODELS_DIR / "pothole" / "weights" / "yolo26m_pothole_best.pt"),
            "sha256": "8e5da7c4c2f9f933f581c3ad8d4c69d23aa2dbd19030b6bf40ac21fdce6f5be1",
            "confidence_threshold": 0.65,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "AVAILABLE",
            "classes": {0: "pothole"},
            "notes": "New YOLO26m production model. Replaces yolov8m_peterhdd. "
                     "Phase 3 benchmark: strong false-positive suppression on complex road textures.",
        },
        "pothole_yolov8_peterhdd": {
            "display_name": "YOLOv8m Pothole (Previous Production)",
            "task": "POTHOLE",
            "architecture": "YOLOv8m",
            "version": "legacy",
            "model_path": str(MODELS_DIR / "pothole" / "weights" / "pothole_yolov8_peterhdd.pt"),
            "sha256": "af2ac6ce7bfec72e71643659ac946caf80ced84869e526a60135c457abfbb200",
            "confidence_threshold": 0.65,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "AVAILABLE",
            "classes": {0: "pothole"},
            "notes": "Hugging Face peterhdd model. Massive reduction in false positives on complex road "
                     "textures vs yolo26n. Previously production; now superseded by YOLO26m.",
        },
        "pothole_yolov8m_hardnegative_v1": {
            "display_name": "YOLOv8m Hard-Negative Fine-tune V1",
            "task": "POTHOLE",
            "architecture": "YOLOv8m",
            "version": "v1",
            "model_path": str(MODELS_DIR / "pothole" / "weights" / "pothole_yolov8m_hardnegative_v1.pt"),
            "sha256": "",  # Compute on first use
            "confidence_threshold": 0.65,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "AVAILABLE",
            "classes": {0: "pothole"},
            "notes": "Fine-tuned on hard-negative examples to reduce false positives. "
                     "Phase 3 retrain v3_gentle variant.",
        },
        "pothole_yolo26n_640": {
            "display_name": "YOLO26n 640px (Deprecated — Noisy)",
            "task": "POTHOLE",
            "architecture": "YOLO26n",
            "version": "n640",
            "model_path": str(MODELS_DIR / "pothole" / "weights" / "pothole_yolo26n_640.pt"),
            "sha256": "",  # Compute on first use
            "confidence_threshold": 0.65,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "DEPRECATED",
            "classes": {0: "pothole"},
            "notes": "Native 640px training. DEPRECATED: Extremely noisy on empty roads with complex "
                     "textures (1700+ raw detections in Phase 2 testing). Do not use for production.",
        },
        "pothole_yolov8n_256": {
            "display_name": "YOLOv8n 256px (Deprecated — Inferior)",
            "task": "POTHOLE",
            "architecture": "YOLOv8n",
            "version": "n256",
            "model_path": str(MODELS_DIR / "pothole" / "weights" / "pothole_yolov8n_256.pt"),
            "sha256": "",  # Compute on first use
            "confidence_threshold": 0.65,
            "iou_threshold": 0.45,
            "imgsz": 256,
            "device": "auto",
            "status": "DEPRECATED",
            "classes": {0: "pothole"},
            "notes": "Native 256px training. DEPRECATED: Severe resolution mismatch when run at 640px. "
                     "Inferior to all other registered pothole models.",
        },
    },

    # ================================================================
    # WATERLOGGING — segmentation
    # ================================================================
    "WATERLOGGING": {
        "waterlogging_v2": {
            "display_name": "Waterlogging Segmentation V2 (Active)",
            "task": "WATERLOGGING",
            "architecture": "YOLOv8n-seg",
            "version": "v2",
            "model_path": str(PROJECT_ROOT / "runs" / "segment" / "models" / "waterlogging" / "v2" / "weights" / "best.pt"),
            "sha256": "b8698dcd0683b8794a56a45cea56c2a66f76d322decccaee720da8c23b39922a",
            "confidence_threshold": 0.55,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "TEST_MODE",
            "classes": {0: "waterlogging"},
            "notes": "V2 trained on 6 diverse video sources with proper video-level train/val/test split. "
                     "Val metrics on genuinely unseen data: Mask mAP50=72.8%, mAP50-95=57.3%, "
                     "Box P=0.951, R=0.649. EXPERIMENTAL — not production validated.",
        },
        "waterlogging_v1": {
            "display_name": "Waterlogging Segmentation V1",
            "task": "WATERLOGGING",
            "architecture": "YOLOv8n-seg",
            "version": "v1",
            "model_path": str(PROJECT_ROOT / "runs" / "segment" / "models" / "waterlogging" / "v1" / "weights" / "best.pt"),
            "sha256": "a2a1b13cc42f4f86ba4ec0f0bdfc524065bce5291eb3e698c56d3cdcdb968694",
            "confidence_threshold": 0.40,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "TEST_MODE",
            "classes": {0: "waterlogging"},
            "notes": "First waterlogging segmentation model. Superseded by V2. "
                     "TEST MODE — no production validation metrics available.",
        },
    },

    # ================================================================
    # OBJECT — vehicle + person detection (shared COCO model)
    # Traffic density is DERIVED from this detector — not a separate model.
    # ================================================================
    "OBJECT": {
        "yolov8n": {
            "display_name": "YOLOv8n Object Detector (COCO)",
            "task": "OBJECT",
            "architecture": "YOLOv8n",
            "version": "ultralytics-pretrained",
            "model_path": str(BACKEND_DIR / "yolov8n.pt"),
            "sha256": "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
            "confidence_threshold": 0.30,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "AVAILABLE",
            "classes": {
                0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
                5: "bus", 7: "truck"
            },
            "notes": "Ultralytics pretrained on COCO. Detects vehicles (car, bus, truck, motorcycle, "
                     "bicycle) and persons. Traffic density is DERIVED from vehicle detections — "
                     "it is not a separate trained model. License: AGPL-3.0.",
        },
        "indian_vehicles_yolov8n": {
            "display_name": "YOLOv8n Indian Traffic + Auto-Rickshaw (Option A)",
            "task": "OBJECT",
            "architecture": "YOLOv8n",
            "version": "indian-traffic-v1",
            "model_path": str(MODELS_DIR / "vehicle" / "indian_vehicles_yolov8n.pt"),
            "sha256": "",
            "confidence_threshold": 0.35,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "UNAVAILABLE",  # Will flip to AVAILABLE when weights are downloaded
            "classes": {
                0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
                5: "bus", 7: "truck", 8: "auto_rickshaw"
            },
            "notes": "Option A: Pre-trained on Indian traffic datasets. Capable of classifying "
                     "auto-rickshaws natively, resolving the tracking classification flicker.",
        },
    },

    # ================================================================
    # HELMET — helmet / no-helmet detection
    # ================================================================
    "HELMET": {
        "best_roadx": {
            "display_name": "Helmet / No-Helmet Detector (best_roadx)",
            "task": "HELMET",
            "architecture": "YOLOv8",
            "version": "roadx",
            "model_path": str(MODELS_DIR / "helmet" / "weights" / "best_roadx.pt"),
            "sha256": "",
            "confidence_threshold": 0.40,
            "iou_threshold": 0.45,
            "imgsz": 640,
            "device": "auto",
            "status": "UNAVAILABLE",
            "classes": {
                0: "helmet",
                1: "nohelmet",
                2: "licenseplate",  # suppressed from UI
                3: "motorcyclist",  # internal tracking only
            },
            "notes": "best_roadx.pt is ABSENT from disk (confirmed Phase 5 audit). "
                     "Do NOT substitute another model without Phase benchmarking evidence. "
                     "HelmetDetector gracefully disables when this file is absent. "
                     "Classes: helmet→HELMET event, nohelmet→NO_HELMET event, "
                     "licenseplate→suppressed, motorcyclist→internal only.",
        },
    },
}

# ---------------------------------------------------------------------------
# Default active model for each task
# (loaded when no config file exists or config is corrupt)
# WATERLOGGING corrected to v2 (what the detector actually uses)
# ---------------------------------------------------------------------------
DEFAULT_ACTIVE: Dict[str, str] = {
    "POTHOLE":     "yolo26m_pothole_best",
    "WATERLOGGING":"waterlogging_v2",
    "OBJECT":      "yolov8n",
    "HELMET":      "best_roadx",
}


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------

def load_active_config() -> Dict[str, Any]:
    """Load active model selection from disk, falling back to defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                stored = json.load(f)
            result = DEFAULT_ACTIVE.copy()
            # Accept string or dict
            for task, val in stored.items():
                if task in REGISTERED_MODELS:
                    mid = val.get("model_id") if isinstance(val, dict) else val
                    if mid in REGISTERED_MODELS[task]:
                        result[task] = val
            return result
        except (json.JSONDecodeError, KeyError):
            logger.warning("[REGISTRY] active_config.json corrupt — using defaults")
    return DEFAULT_ACTIVE.copy()


def save_active_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _save_previous_config(config: Dict[str, Any]) -> None:
    """Persist the pre-switch state for rollback."""
    with open(PREVIOUS_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def load_previous_config() -> Dict[str, Any]:
    """Load the previous config (used for rollback)."""
    if PREVIOUS_CONFIG_PATH.exists():
        try:
            with open(PREVIOUS_CONFIG_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_active_model(task: str, model_id: str, confidence_threshold: Optional[float] = None) -> bool:
    """
    Switch the active model for a task.

    Validates task and model_id against the registry.
    Saves the previous active state to allow rollback.
    Does NOT reload any running model cache — takes effect on next server
    startup or explicit cache invalidation.
    """
    if task not in REGISTERED_MODELS:
        raise ValueError(f"Unknown task: {task}. Valid tasks: {list(REGISTERED_MODELS)}")
    if model_id not in REGISTERED_MODELS[task]:
        raise ValueError(
            f"Unknown model_id '{model_id}' for task '{task}'. "
            f"Valid: {list(REGISTERED_MODELS[task])}"
        )

    current = load_active_config()
    _save_previous_config(current)

    val = {"model_id": model_id}
    if confidence_threshold is not None:
        val["confidence_threshold"] = confidence_threshold

    current[task] = val
    save_active_config(current)
    logger.info("[REGISTRY] Model switch: %s → %s (conf=%s)", task, model_id, confidence_threshold)
    return True


def rollback_active_model(task: str) -> Optional[str]:
    """
    Rollback the active model for a task to its previous selection.
    Returns the new (rolled-back) model_id, or None if no previous state.
    """
    previous = load_previous_config()
    if task not in previous:
        return None
    prev_val = previous[task]
    prev_model_id = prev_val.get("model_id") if isinstance(prev_val, dict) else prev_val
    if task not in REGISTERED_MODELS or prev_model_id not in REGISTERED_MODELS[task]:
        return None

    current = load_active_config()
    _save_previous_config(current)
    current[task] = prev_val
    save_active_config(current)
    logger.info("[REGISTRY] Rollback: %s → %s", task, prev_model_id)
    return prev_model_id


def get_active_model(task: str) -> Dict[str, Any]:
    """
    Return the full registry entry for the currently active model for a task.

    Raises RuntimeError on SHA256 mismatch.
    SHA256 is only computed once per process (cached in _sha256_cache).
    """
    config = load_active_config()
    val = config.get(task)
    
    if isinstance(val, dict):
        model_id = val.get("model_id")
        override_conf = val.get("confidence_threshold")
    else:
        model_id = val
        override_conf = None

    if not model_id or model_id not in REGISTERED_MODELS.get(task, {}):
        model_id = DEFAULT_ACTIVE.get(task)
        override_conf = None

    if not model_id:
        raise ValueError(f"No model configured for task: {task}")

    model_data = REGISTERED_MODELS[task][model_id].copy()
    model_data["model_id"] = model_id
    if override_conf is not None:
        model_data["confidence_threshold"] = override_conf

    model_path  = model_data["model_path"]
    expected_sha = model_data.get("sha256", "")
    status      = model_data.get("status", "")

    if status == "UNAVAILABLE":
        # Gracefully report as unavailable — do not fail the caller
        logger.warning("[REGISTRY] Model %s (%s) is UNAVAILABLE — file absent.", model_id, task)
        return model_data

    # Verify file exists
    if not Path(model_path).exists():
        raise RuntimeError(
            f"[MODEL REGISTRY] Model file not found: {model_path}\n"
            f"Task: {task}, Model ID: {model_id}"
        )

    # SHA256 integrity check (cached after first computation)
    if expected_sha:
        actual_sha = _calculate_sha256(model_path)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"[MODEL REGISTRY] SHA256 MISMATCH for {model_id}.\n"
                f"Expected: {expected_sha}\n"
                f"Actual:   {actual_sha}\n"
                f"Path:     {model_path}\n"
                "REFUSING to load potentially corrupted or substituted model."
            )

    return model_data


def get_all_models() -> Dict[str, Any]:
    """
    Return all registered models annotated with is_active, file_exists,
    and previous_active flags. Used by the Model Lab frontend.
    """
    active  = load_active_config()
    previous = load_previous_config()
    result: Dict[str, Any] = {}

    for task, models in REGISTERED_MODELS.items():
        result[task] = {}
        for mid, data in models.items():
            entry = data.copy()
            entry["model_id"] = mid
            
            active_val = active.get(task)
            if isinstance(active_val, dict):
                is_active = (active_val.get("model_id") == mid)
                if is_active and "confidence_threshold" in active_val:
                    entry["confidence_threshold"] = active_val["confidence_threshold"]
            else:
                is_active = (active_val == mid)
                
            prev_val = previous.get(task)
            is_previous = (prev_val.get("model_id") == mid) if isinstance(prev_val, dict) else (prev_val == mid)

            entry["is_active"]      = is_active
            entry["is_previous"]    = is_previous
            entry["file_exists"]    = Path(data["model_path"]).exists()
            result[task][mid] = entry

    return result
