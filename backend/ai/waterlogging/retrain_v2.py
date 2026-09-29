#!/usr/bin/env python3
"""
Phase 10 — Step 18: Retrain waterlogging model on V2 dataset.

PREREQUISITE: Annotation must be complete first!
  - images/train/ frames must have corresponding labels/train/*.txt files
  - images/val/ frames must have corresponding labels/val/*.txt files
  - Empty label files = no waterlogging annotation for that frame (negatives)

This script:
1. Verifies annotations exist before starting
2. Merges negative frames into the splits
3. Trains YOLOv8n-seg with versioned output
4. Saves metadata.json with sha256 for the model registry (Step 1 invariant)
5. Runs validation on VAL set immediately after training

Run from project root:
  python3 backend/ai/waterlogging/retrain_v2.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import shutil
from pathlib import Path
import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT   = Path(__file__).resolve().parents[3]
DATASET_DIR = REPO_ROOT / "backend" / "data" / "waterlogging" / "yolo_dataset_v2"
DATA_YAML   = DATASET_DIR / "data.yaml"
MODELS_DIR  = REPO_ROOT / "runs" / "segment" / "models" / "waterlogging"
VERSION     = "v2"
OUT_DIR     = MODELS_DIR / VERSION


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()


def check_annotations() -> tuple[int, int]:
    """Verify annotations exist. Returns (annotated_count, total_count)."""
    labels_train = DATASET_DIR / "labels" / "train"
    if not labels_train.exists():
        logger.error("labels/train/ does not exist. Run build_dataset_v2.py first.")
        sys.exit(1)

    label_files = list(labels_train.glob("*.txt"))
    # A real annotation has content; empty file = unannotated placeholder
    annotated = [f for f in label_files if f.stat().st_size > 0]
    logger.info("Annotation check: %d/%d train label files have content", len(annotated), len(label_files))

    if len(annotated) == 0:
        logger.error(
            "NO ANNOTATIONS FOUND. All %d label files are empty placeholders.\n"
            "You must annotate the training images first using:\n"
            "  labelImg (YOLO segmentation mode)\n"
            "  OR upload images/train/ to Roboflow / CVAT\n"
            "After annotation, place the .txt label files in labels/train/",
            len(label_files)
        )
        sys.exit(1)

    if len(annotated) < 50:
        logger.warning(
            "Only %d annotated frames found. This is likely insufficient for robust training. "
            "Recommend at least 150+ annotated positive frames before retraining.",
            len(annotated)
        )
    return len(annotated), len(label_files)


def merge_negatives():
    """Merge hard-negative frames into train/val splits."""
    for split in ["train", "val"]:
        neg_images = DATASET_DIR / "images" / f"{split}_negatives"
        neg_labels = DATASET_DIR / "labels" / f"{split}_negatives"
        dst_images = DATASET_DIR / "images" / split
        dst_labels = DATASET_DIR / "labels" / split

        if not neg_images.exists():
            continue

        count = 0
        for img_path in neg_images.glob("*.jpg"):
            dst_img = dst_images / img_path.name
            if not dst_img.exists():
                shutil.copy2(img_path, dst_img)
                count += 1
            # Corresponding empty label
            label_path = neg_labels / (img_path.stem + ".txt") if neg_labels.exists() else None
            dst_lbl = dst_labels / (img_path.stem + ".txt")
            if not dst_lbl.exists():
                dst_lbl.touch()

        if count > 0:
            logger.info("Merged %d hard-negative frames into %s split", count, split)


def retrain():
    annotated, total = check_annotations()
    logger.info("Starting V2 retraining with %d annotated positive frames", annotated)

    merge_negatives()

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed: pip install ultralytics")
        sys.exit(1)

    # Start from V1 weights (fine-tune, don't start from scratch)
    v1_weights = MODELS_DIR / "v1" / "weights" / "best.pt"
    if v1_weights.exists():
        logger.info("Fine-tuning from V1 weights: %s", v1_weights)
        base_model = str(v1_weights)
    else:
        logger.info("V1 weights not found, starting from yolov8n-seg.pt pretrained")
        base_model = "yolov8n-seg.pt"

    model = YOLO(base_model)

    # Clean previous v2 output if exists
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    logger.info("Training YOLOv8n-seg V2 ...")
    results = model.train(
        data=str(DATA_YAML),
        epochs=30,           # More epochs than V1 (15) since dataset is bigger and diverse
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

    # Verify output exists
    best_pt = OUT_DIR / "weights" / "best.pt"
    if not best_pt.exists():
        logger.error("Training failed: best.pt not found at %s", best_pt)
        sys.exit(1)

    # Compute sha256 for model registry (Step 1 invariant)
    checksum = _sha256(best_pt)
    logger.info("V2 model sha256: %s", checksum)

    # Write versioned metadata.json
    metrics = {}
    try:
        results_csv = OUT_DIR / "results.csv"
        if results_csv.exists():
            import csv
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
        "architecture": "YOLOv8n-seg",
        "base_model": base_model,
        "training_date": datetime.datetime.now().isoformat(),
        "dataset": str(DATA_YAML),
        "dataset_version": "v2",
        "positive_videos_train": [
            "17929886-uhd_3840_2160_59fps_compressed.mp4",
            "car-driving-through-a-flooded-street-in-during-a-flooding.mp4",
            "cars-driving-street-flooded-during-a-flooding-in-thailand.mp4",
        ],
        "positive_videos_val": [
            "traffic-on-flooded-road.mp4",
            "16373790_3840_2160_30fps_compressed.mp4",
        ],
        "positive_videos_test": [
            "car-driving-through-a-flooded-street-in-during-a-flooding-2.mp4",
        ],
        "annotated_train_frames": annotated,
        "total_train_frames": total,
        "epochs": 30,
        "imgsz": 640,
        "batch": 4,
        "final_metrics": metrics,
        "sha256": checksum,
        "production_status": "VALIDATION_PENDING",
    }
    meta_path = OUT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Wrote metadata.json to %s", meta_path)

    logger.info("="*60)
    logger.info("V2 TRAINING COMPLETE")
    logger.info("Model: %s", best_pt)
    logger.info("SHA256: %s", checksum)
    logger.info("="*60)
    logger.info("NEXT STEP: Run Step 19 calibration sweep:")
    logger.info("  python3 backend/ai/waterlogging/calibrate_thresholds.py")


if __name__ == "__main__":
    retrain()
