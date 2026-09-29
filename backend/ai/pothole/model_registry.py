"""
Urban Watch — Pothole Model Registry

Maintains validated pothole models, their configurations, and lifecycle status.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.pothole.config import AUDITED_MODELS, DEFAULT_POTHOLE_MODEL
from ai.pothole.model_inspector import inspect_pothole_model


class PotholeModelRegistry:
    """Registry managing available pothole models and metadata."""

    def __init__(self) -> None:
        self._models: Dict[str, Dict[str, Any]] = dict(AUDITED_MODELS)

    def register(self, key: str, path: str, status: str = "AUDITED") -> Dict[str, Any]:
        """Inspect and register a model checkpoint."""
        info = inspect_pothole_model(path)
        if not info["valid"]:
            raise ValueError(f"Cannot register invalid model: {info.get('rejection_reason')}")
        
        entry = {
            "path": path,
            "family": info.get("architecture", "Unknown"),
            "native_imgsz": info.get("trained_imgsz", 640),
            "classes": info.get("names", {}),
            "status": status,
            "parameters": info.get("parameters", 0),
            "file_size_mb": info.get("file_size_mb", 0.0)
        }
        self._models[key] = entry
        return entry

    def get(self, key: str = "yolo26n_640") -> Dict[str, Any]:
        if key not in self._models:
            raise KeyError(f"Pothole model '{key}' not registered. Available: {list(self._models.keys())}")
        return self._models[key]

    def get_default_model_path(self) -> str:
        return DEFAULT_POTHOLE_MODEL

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"key": k, **v} for k, v in self._models.items()]


# Global singleton registry
pothole_registry = PotholeModelRegistry()
