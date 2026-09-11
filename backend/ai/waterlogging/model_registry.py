"""
Urban Watch — Waterlogging Model Registry
Phase 10 Step 1: Enforced checksum invariant.

The production loader ASSERTS the model's sha256 matches the recorded metadata.
If it does not match, a loud RuntimeError is raised. No silent fallback.
This directly prevents the class of bug where the wrong .pt file is loaded
without anyone noticing (e.g. best.pt vs best_roadx.pt substring mismatch).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Canonical metadata location
WATERLOGGING_MODELS_DIR = Path(__file__).resolve().parents[3] / "runs" / "segment" / "models" / "waterlogging"


def _sha256(file_path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def create_version_metadata(version: str, model_path: Path) -> dict:
    """Create metadata.json for a newly frozen model version."""
    checksum = _sha256(model_path)
    metadata = {
        "version": version,
        "model_filename": model_path.name,
        "model_path": str(model_path),
        "architecture": "YOLOv8n-seg",
        "task": "segment",
        "yolo_version": "8",
        "detection_type": "segmentation",
        "training_dataset": "backend/data/waterlogging/yolo_dataset",
        "training_video_source": "17929886-uhd_3840_2160_59fps_compressed.mp4",
        "dataset_frames": 95,
        "epochs": 15,
        "imgsz": 640,
        "batch": 4,
        "optimizer": "auto",
        "confidence_threshold": 0.40,
        "iou_threshold": 0.45,
        "classes": {0: "waterlogging"},
        "final_metrics": {
            "box_mAP50": 0.97902,
            "box_mAP50_95": 0.83183,
            "mask_mAP50": 0.97841,
            "mask_mAP50_95": 0.78329,
        },
        "known_limitations": (
            "SINGLE-SOURCE TRAINING DATA. Precision=0.00 on unseen video. "
            "NOT production-ready. Do not enable WATERLOGGING_ENABLED until "
            "Phase 10 Steps 1-21 acceptance criteria are met."
        ),
        "sha256": checksum,
        "production_status": "DISABLED_PHASE10_SAFETY",
    }
    return metadata


def write_version_metadata(version: str, model_path: Path) -> Path:
    """Write metadata.json to the versioned model directory."""
    version_dir = WATERLOGGING_MODELS_DIR / version
    version_dir.mkdir(parents=True, exist_ok=True)
    metadata = create_version_metadata(version, model_path)
    meta_path = version_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Wrote waterlogging model metadata to %s", meta_path)
    return meta_path


def load_and_verify_model(version: str = "v1") -> Path:
    """
    Load the model path for the given version and ASSERT the sha256 matches.

    Raises RuntimeError loudly if:
    - metadata.json does not exist
    - model file does not exist
    - sha256 does not match

    This is an enforced invariant, not just a log warning.
    """
    version_dir = WATERLOGGING_MODELS_DIR / version
    meta_path = version_dir / "metadata.json"
    weights_dir = version_dir / "weights"

    if not meta_path.exists():
        raise RuntimeError(
            f"[WATERLOGGING MODEL REGISTRY] metadata.json not found at {meta_path}. "
            "Run: python3 -m ai.waterlogging.model_registry to initialise it."
        )

    with open(meta_path) as f:
        metadata = json.load(f)

    expected_checksum = metadata.get("sha256")
    if not expected_checksum:
        raise RuntimeError(
            f"[WATERLOGGING MODEL REGISTRY] metadata.json at {meta_path} "
            "has no sha256 field. Re-run model_registry to freeze the checksum."
        )

    model_filename = metadata.get("model_filename", "best.pt")
    model_path = weights_dir / model_filename
    if not model_path.exists():
        raise RuntimeError(
            f"[WATERLOGGING MODEL REGISTRY] Model file not found: {model_path}. "
            "Expected model is missing from disk."
        )

    actual_checksum = _sha256(model_path)
    if actual_checksum != expected_checksum:
        raise RuntimeError(
            f"[WATERLOGGING MODEL REGISTRY] *** SHA256 MISMATCH *** for {model_path}.\n"
            f"  Expected: {expected_checksum}\n"
            f"  Actual:   {actual_checksum}\n"
            "This means the model file on disk has changed since it was frozen. "
            "Do NOT proceed. Check that you are loading the correct model version."
        )

    logger.info(
        "[WATERLOGGING MODEL REGISTRY] Verified %s/%s sha256=%s... OK",
        version, model_filename, actual_checksum[:12]
    )
    return model_path


if __name__ == "__main__":
    """Freeze the current waterlogging v1 model into the registry."""
    import sys
    logging.basicConfig(level=logging.INFO)

    v1_model = WATERLOGGING_MODELS_DIR / "v1" / "weights" / "best.pt"
    if not v1_model.exists():
        print(f"ERROR: Model not found at {v1_model}", file=sys.stderr)
        sys.exit(1)

    meta_file = write_version_metadata("v1", v1_model)
    print(f"Frozen model metadata written to: {meta_file}")

    # Immediately verify the round-trip
    load_and_verify_model("v1")
    print("Verification passed.")
