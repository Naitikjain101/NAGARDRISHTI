#!/usr/bin/env python3
"""
Phase 10 — Pothole Model V2 Retrain
Trains YOLOv8m-det on new annotated pothole dataset.

Run from project root:
  python3 backend/ai/pothole/retrain_v2.py
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
VERSION     = "v2"
OUT_DIR     = MODELS_DIR / VERSION

# Production weights to fine-tune from
V1_WEIGHTS  = REPO_ROOT / "runs" / "detect" / "pothole_hardneg_finetune" / "weights" / "best.pt"
FALLBACK_PT = REPO_ROOT / "backend" / "ai" / "pothole" / "weights" / "pothole_yolov8_peterhdd.pt"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_annotations() -> tuple[int, int]:
    labels_train = DATASET_DIR / "labels" / "train"
    if not labels_train.exists():
        logger.error("labels/train/ missing. Run the annotation tool first.")
        sys.exit(1)
    label_files = list(labels_train.glob("*.txt"))
    annotated = [f for f in label_files if f.stat().st_size > 0 and f.read_text().strip() != "# negative"]
    logger.info("Annotation check: %d/%d train label files have bboxes", len(annotated), len(label_files))
    if len(annotated) == 0:
        logger.error("NO bbox annotations found. Annotate train frames first.")
        sys.exit(1)
    return len(annotated), len(label_files)


def retrain():
    annotated, total = check_annotations()

    # Choose base weights
    if V1_WEIGHTS.exists():
        base_model = str(V1_WEIGHTS)
        logger.info("Fine-tuning from V1 best: %s", V1_WEIGHTS)
    elif FALLBACK_PT.exists():
        base_model = str(FALLBACK_PT)
        logger.info("Fine-tuning from production weights: %s", FALLBACK_PT)
    else:
        base_model = "yolov8m.pt"
        logger.info("Starting from yolov8m.pt pretrained")

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed")
        sys.exit(1)

    model = YOLO(base_model)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    logger.info("Training YOLOv8m-det pothole V2 ...")
    results = model.train(
        data=str(DATA_YAML),
        epochs=25,
        imgsz=640,
        batch=4,
        device="cpu",
        workers=0,
        project=str(MODELS_DIR),
        name=VERSION,
        exist_ok=False,
        pretrained=True,
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
    logger.info("V2 pothole model sha256: %s", checksum)

    # Parse final metrics from results.csv
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
        "dataset_version": "v2",
        "train_videos": ["video_to_road_test.mp4"],
        "val_videos": ["25208-720.mp4"],
        "annotated_train_frames": annotated,
        "total_train_frames": total,
        "epochs": 25,
        "imgsz": 640,
        "final_metrics": metrics,
        "sha256": checksum,
        "production_status": "VALIDATION_PENDING",
    }
    meta_path = OUT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("="*60)
    logger.info("POTHOLE V2 TRAINING COMPLETE")
    logger.info("Model:  %s", best_pt)
    logger.info("SHA256: %s", checksum)
    if metrics:
        map50 = metrics.get("metrics/mAP50(B)", metrics.get("     metrics/mAP50(B)", "N/A"))
        map95 = metrics.get("metrics/mAP50-95(B)", metrics.get("  metrics/mAP50-95(B)", "N/A"))
        logger.info("mAP50:    %s", map50)
        logger.info("mAP50-95: %s", map95)
    logger.info("="*60)
    logger.info("Update config.py to point to: %s", best_pt)


if __name__ == "__main__":
    retrain()
