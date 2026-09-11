"""
Urban Watch — Pothole Model Inspector

Performs static, non-inference inspection of pothole model weights.
Verifies task, class definitions, architecture, parameter count, and native training image size.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import torch

logger = logging.getLogger(__name__)


def inspect_pothole_model(pt_path: str | Path) -> Dict[str, Any]:
    """
    Inspect a pothole model without running inference.

    Parameters
    ----------
    pt_path : str or Path
        Path to the .pt file.

    Returns
    -------
    dict
        Inspection metadata including validity status.
    """
    from ultralytics import YOLO

    pt_path_str = str(pt_path)
    if not os.path.exists(pt_path_str):
        return {
            "path": pt_path_str,
            "valid": False,
            "rejection_reason": f"File does not exist: {pt_path_str}"
        }

    file_size_mb = os.path.getsize(pt_path_str) / (1024 * 1024)

    # 1. Inspect raw checkpoint dictionary
    try:
        ckpt = torch.load(pt_path_str, map_location="cpu", weights_only=False)
        train_args = ckpt.get("train_args", {}) or {}
        imgsz_train = train_args.get("imgsz") if isinstance(train_args, dict) else None
        epoch = ckpt.get("epoch", -1)
        date = ckpt.get("date")
    except Exception as exc:
        return {
            "path": pt_path_str,
            "valid": False,
            "rejection_reason": f"Corrupted or invalid checkpoint format: {exc}"
        }

    # 2. Inspect with YOLO
    try:
        model = YOLO(pt_path_str)
        task = model.task
        names = model.names
        n_params = sum(p.numel() for p in model.model.parameters())
        arch_type = type(model.model).__name__
    except Exception as exc:
        return {
            "path": pt_path_str,
            "valid": False,
            "rejection_reason": f"Failed to instantiate YOLO model: {exc}"
        }

    # 3. Validate task & classes
    if task != "detect":
        return {
            "path": pt_path_str,
            "valid": False,
            "task": task,
            "names": names,
            "rejection_reason": f"Task mismatch: expected 'detect', got '{task}'"
        }

    # Check for 'pothole' class presence
    pothole_class_found = any(
        "pothole" in str(name).lower() for name in names.values()
    )

    if not pothole_class_found:
        return {
            "path": pt_path_str,
            "valid": False,
            "task": task,
            "names": names,
            "rejection_reason": f"Model does not contain 'pothole' class. Classes found: {names}"
        }

    return {
        "path": pt_path_str,
        "valid": True,
        "model_name": Path(pt_path_str).stem,
        "task": task,
        "names": names,
        "num_classes": len(names),
        "parameters": n_params,
        "architecture": arch_type,
        "file_size_mb": round(file_size_mb, 2),
        "trained_imgsz": imgsz_train,
        "epoch": epoch,
        "training_date": date
    }
