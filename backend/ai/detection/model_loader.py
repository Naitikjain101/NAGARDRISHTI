"""
Urban Watch — Model Loader

Responsibilities:
- Load pretrained models from Ultralytics Hub or local path
- Inspect model metadata (task, names, parameters)
- Validate that required classes are present
- Record license, source, parameter count
- Reject models that fail validation

Rules (from MODEL_POLICY.md):
1. Never trust model filenames — always inspect model.names
2. Never fabricate class presence — only accept what model.names shows
3. Record license and source for every accepted model
4. Reject models that don't contain required classes
5. Log rejection reasons explicitly
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from ai.common.schemas import ModelInspectionResult
from ai.detection.classes import validate_required_classes, PHASE1_REQUIRED_CLASSES

logger = logging.getLogger(__name__)

# Ultralytics license for pretrained models (AGPL-3.0).
# Source: https://github.com/ultralytics/ultralytics/blob/main/LICENSE
ULTRALYTICS_LICENSE = "AGPL-3.0"
ULTRALYTICS_SOURCE = "https://github.com/ultralytics/ultralytics"

# Expected task for detection models
DETECTION_TASK = "detect"


class ModelLoadError(Exception):
    """Raised when a model fails to load or validate."""
    pass


def inspect_model(
    pt_file: str | Path,
    required_classes: set[str] | None = None,
) -> ModelInspectionResult:
    """
    Load a model and return its full inspection result.

    This is a pure inspection — does NOT run any inference.

    Parameters
    ----------
    pt_file : str or Path
        Model filename (e.g. "yolo11n.pt") or full path.
        If just a filename, Ultralytics will download from Hub if not cached.
    required_classes : set[str], optional
        Classes that must be present. Defaults to PHASE1_REQUIRED_CLASSES.

    Returns
    -------
    ModelInspectionResult
        Full inspection result including acceptance/rejection status.
    """
    from ultralytics import YOLO  # lazy import — heavy package

    if required_classes is None:
        required_classes = PHASE1_REQUIRED_CLASSES

    pt_file = str(pt_file)
    result = ModelInspectionResult(
        model_name=Path(pt_file).stem,
        pt_file=pt_file,
        source_url=ULTRALYTICS_SOURCE,
        license=ULTRALYTICS_LICENSE,
    )

    # -------------------------------------------------------------------------
    # Step 1: Load model and measure load time
    # -------------------------------------------------------------------------
    logger.info("Inspecting model: %s", pt_file)
    t0 = time.perf_counter()

    try:
        model = YOLO(pt_file)
    except Exception as exc:
        reason = f"Failed to load model: {exc}"
        logger.error("REJECTED %s — %s", pt_file, reason)
        return result.model_copy(update={
            "rejection_reason": reason,
            "accepted": False,
        })

    load_time_ms = (time.perf_counter() - t0) * 1000.0
    logger.info("Loaded %s in %.1f ms", pt_file, load_time_ms)

    # -------------------------------------------------------------------------
    # Step 2: Extract model metadata
    # -------------------------------------------------------------------------
    try:
        task = getattr(model, "task", None)
        names: dict[int, str] = getattr(model, "names", {})
        num_classes = len(names)

        # Parameter count — use model.info() if available
        num_params = None
        try:
            info = model.info(verbose=False)
            # model.info() returns (layers, params, gradients, flops) tuple
            if isinstance(info, (tuple, list)) and len(info) >= 2:
                num_params = int(info[1])
        except Exception:
            num_params = None

        # Model file size
        model_size_mb = None
        try:
            local_path = _find_cached_model(pt_file)
            if local_path and os.path.exists(local_path):
                model_size_mb = round(os.path.getsize(local_path) / (1024 * 1024), 2)
        except Exception:
            model_size_mb = None

    except Exception as exc:
        reason = f"Failed to extract model metadata: {exc}"
        logger.error("REJECTED %s — %s", pt_file, reason)
        return result.model_copy(update={
            "rejection_reason": reason,
            "accepted": False,
            "load_time_ms": load_time_ms,
        })

    logger.info(
        "Model %s: task=%s, classes=%d, params=%s",
        pt_file, task, num_classes, num_params,
    )

    # -------------------------------------------------------------------------
    # Step 3: Validate task
    # -------------------------------------------------------------------------
    if task != DETECTION_TASK:
        reason = (
            f"Task mismatch: expected '{DETECTION_TASK}', "
            f"got '{task}'. Model cannot be used for object detection."
        )
        logger.warning("REJECTED %s — %s", pt_file, reason)
        return result.model_copy(update={
            "task": task,
            "classes": names,
            "num_classes": num_classes,
            "num_parameters": num_params,
            "model_size_mb": model_size_mb,
            "load_time_ms": load_time_ms,
            "rejection_reason": reason,
            "accepted": False,
        })

    # -------------------------------------------------------------------------
    # Step 4: Validate required classes
    # -------------------------------------------------------------------------
    all_present, missing = validate_required_classes(names, required_classes)

    if not all_present:
        reason = (
            f"Missing required classes: {missing}. "
            "This model cannot be used for Phase 1 traffic detection."
        )
        logger.warning("REJECTED %s — %s", pt_file, reason)
        return result.model_copy(update={
            "task": task,
            "classes": names,
            "num_classes": num_classes,
            "num_parameters": num_params,
            "model_size_mb": model_size_mb,
            "load_time_ms": load_time_ms,
            "required_classes_present": False,
            "missing_classes": missing,
            "rejection_reason": reason,
            "accepted": False,
        })

    # -------------------------------------------------------------------------
    # Step 5: Accept model
    # -------------------------------------------------------------------------
    logger.info(
        "ACCEPTED %s — task=%s, %d classes, %s params, %.1f ms load",
        pt_file, task, num_classes, num_params, load_time_ms,
    )

    return result.model_copy(update={
        "task": task,
        "classes": names,
        "num_classes": num_classes,
        "num_parameters": num_params,
        "model_size_mb": model_size_mb,
        "load_time_ms": load_time_ms,
        "required_classes_present": True,
        "missing_classes": [],
        "rejection_reason": None,
        "accepted": True,
        "notes": (
            f"License: {ULTRALYTICS_LICENSE}. "
            f"Source: {ULTRALYTICS_SOURCE}. "
            "Acceptable for SIH prototype (non-commercial)."
        ),
    })


def load_model(pt_file: str | Path, device: str = "cpu"):
    """
    Load a YOLO model onto the specified device.

    Parameters
    ----------
    pt_file : str or Path
        Model filename or path.
    device : str
        Torch device string: "cuda:0", "mps", "cpu".

    Returns
    -------
    YOLO model instance, ready for inference.

    Raises
    ------
    ModelLoadError
        If the model cannot be loaded.
    """
    from ultralytics import YOLO

    pt_file = str(pt_file)
    logger.info("Loading model %s on device=%s", pt_file, device)

    try:
        model = YOLO(pt_file)
        # Move model to device — Ultralytics handles this via .to() or device param
        model.to(device)
        logger.info("Model %s loaded on %s", pt_file, device)
        return model
    except Exception as exc:
        raise ModelLoadError(f"Cannot load {pt_file} on {device}: {exc}") from exc


def _find_cached_model(pt_file: str) -> str | None:
    """
    Try to find the cached .pt file after Ultralytics downloads it.
    Returns the path if found, None otherwise.
    """
    # Ultralytics caches models in ~/.cache/ultralytics/ or current directory
    candidates = [
        pt_file,
        os.path.join(os.getcwd(), pt_file),
        os.path.expanduser(f"~/.cache/ultralytics/{pt_file}"),
        os.path.expanduser(f"~/Library/Caches/ultralytics/{pt_file}"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None
