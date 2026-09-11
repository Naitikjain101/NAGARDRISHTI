#!/usr/bin/env python3
"""
Phase 10 — Pothole Model V3 Gentle Retrain
Attempts to fine-tune the production pothole model on the new 65 frames
WITHOUT catastrophic forgetting. We do this by freezing the backbone and
using a very small learning rate.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT   = Path(__file__).resolve().parents[3]
DATASET_DIR = REPO_ROOT / "backend" / "data" / "pothole" / "yolo_dataset_v2"
DATA_YAML   = DATASET_DIR / "data.yaml"
MODELS_DIR  = REPO_ROOT / "runs" / "detect" / "models" / "pothole"
VERSION     = "v3_gentle"
OUT_DIR     = MODELS_DIR / VERSION

# The production model we want to improve
FALLBACK_PT = REPO_ROOT / "backend" / "ai" / "pothole" / "weights" / "pothole_yolov8_peterhdd.pt"

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def retrain():
    base_model = str(FALLBACK_PT)
    if not FALLBACK_PT.exists():
        logger.error("Base model not found: %s", FALLBACK_PT)
        sys.exit(1)
    
    logger.info("Fine-tuning gently from production weights: %s", FALLBACK_PT)

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed")
        sys.exit(1)

    model = YOLO(base_model)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    logger.info("Training YOLOv8m-det pothole V3 (Gentle Fine-tuning)...")
    # freeze=10 freezes the backbone (layers 0-9) so it retains general pothole knowledge.
    # lr0=0.001 is 1/10th the default learning rate to prevent destroying existing weights.
    results = model.train(
        data=str(DATA_YAML),
        epochs=15,          # Shorter training to prevent overfitting
        imgsz=640,
        batch=4,
        device="cpu",
        workers=0,
        project=str(MODELS_DIR),
        name=VERSION,
        exist_ok=False,
        pretrained=True,
        freeze=10,          # Freeze backbone
        lr0=0.001,          # Very small learning rate
        optimizer="auto",
        verbose=True,
        seed=42,
        save=True,
        plots=True,
    )

    best_pt = OUT_DIR / "weights" / "best.pt"
    if not best_pt.exists():
        logger.error("Training failed: best.pt not found at %s", best_pt)
        sys.exit(1)

    checksum = _sha256(best_pt)
    logger.info("V3 gentle model sha256: %s", checksum)

    # Parse final metrics
    metrics = {}
    try:
        results_csv = OUT_DIR / "results.csv"
        if results_csv.exists():
            with open(results_csv) as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                metrics = {k.strip(): float(v) for k, v in last.items() if v.strip()}
    except Exception as e:
        logger.warning("Could not parse results.csv: %s", e)

    metadata = {
        "version": VERSION,
        "model_filename": "best.pt",
        "model_path": str(best_pt),
        "architecture": "YOLOv8m-det",
        "base_model": base_model,
        "training_date": datetime.datetime.now().isoformat(),
        "dataset": str(DATA_YAML),
        "epochs": 15,
        "freeze": 10,
        "lr0": 0.001,
        "final_metrics": metrics,
        "sha256": checksum,
    }
    meta_path = OUT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("="*60)
    logger.info("POTHOLE V3 GENTLE TRAINING COMPLETE")
    logger.info("Model:  %s", best_pt)
    if metrics:
        map50 = metrics.get("metrics/mAP50(B)", "N/A")
        logger.info("mAP50:    %s", map50)
    logger.info("="*60)

if __name__ == "__main__":
    retrain()
