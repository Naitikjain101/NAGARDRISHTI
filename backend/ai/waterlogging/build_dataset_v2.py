#!/usr/bin/env python3
"""
Phase 10 — Steps 15, 16, 17: Dataset Rebuild Script
Extracts frames from positive and hard-negative videos,
builds a proper VIDEO-LEVEL train/val/test split,
and writes a corrected YOLO data.yaml.

This fixes the critical Phase 10 finding:
  train == val (same files) → model memorizes, doesn't generalize

New split (video-level, no leakage):
  TRAIN  : 17929886 (original), car-driving-flooding, cars-driving-thailand
  VAL    : traffic-on-flooded-road, 16373790_compressed
  TEST   : car-driving-flooding-2  ← genuinely held-out
  NEG-TRAIN: 20260902_081615, 20260902_083213, traffic_test-2-2-2
  NEG-VAL:   20260902_083003

Run from project root:
  python3 backend/ai/waterlogging/build_dataset_v2.py
"""
from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT / "backend" / "data" / "waterlogging"
RAW_DIR   = DATA_ROOT / "raw"
HN_DIR    = DATA_ROOT / "hard_negatives"
DATASET_DIR = DATA_ROOT / "yolo_dataset_v2"

# Sampling: extract 1 frame every N frames
POSITIVE_INTERVAL = 20    # ~1.5fps from 30fps sources
NEGATIVE_INTERVAL = 30    # more sparse for negatives (we have more footage)

# VIDEO-LEVEL SPLIT (Step 17: corrected split, no leakage)
TRAIN_POSITIVES = [
    "17929886-uhd_3840_2160_59fps_compressed.mp4",          # original training video
    "car-driving-through-a-flooded-street-in-during-a-flooding.mp4",   # Thailand flood 1
    "cars-driving-street-flooded-during-a-flooding-in-thailand.mp4",   # Thailand flood 2
]
VAL_POSITIVES = [
    "traffic-on-flooded-road.mp4",                           # Indian waterlogging
    "16373790_3840_2160_30fps_compressed.mp4",               # Indian city flood
]
TEST_POSITIVES = [
    "car-driving-through-a-flooded-street-in-during-a-flooding-2.mp4", # Thailand flood 3 (held-out)
]

TRAIN_NEGATIVES = [
    "20260902_081615.mp4",    # dry Indian road (phone)
    "20260902_083213.mp4",    # dry Indian road (motorcycles)
    "traffic_test-2-2-2.mp4", # dry Indian highway
]
VAL_NEGATIVES = [
    "20260902_083003.mp4",    # dry Indian road (zebra crossing)
]


def extract_frames(video_path: Path, out_dir: Path, interval: int, prefix: str) -> list[Path]:
    """Extract frames at given interval. Returns list of saved paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    saved = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            fname = out_dir / f"{prefix}_f{frame_idx:06d}.jpg"
            cv2.imwrite(str(fname), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved.append(fname)
        frame_idx += 1
    cap.release()
    print(f"  {video_path.name}: {len(saved)} frames extracted (total={total})")
    return saved


def build_split(split_name: str, pos_videos: list[str], neg_videos: list[str],
                pos_interval: int, neg_interval: int):
    """Extract frames for one split, put positives in images/ and negatives (unannotated) in negatives/."""
    print(f"\n=== Building {split_name} split ===")
    images_dir = DATASET_DIR / "images" / split_name
    labels_dir = DATASET_DIR / "labels" / split_name
    negs_dir   = DATASET_DIR / "images" / f"{split_name}_negatives"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    negs_dir.mkdir(parents=True, exist_ok=True)

    all_pos_frames = []
    for vid_name in pos_videos:
        vid_path = RAW_DIR / vid_name
        if not vid_path.exists():
            print(f"  WARNING: {vid_name} not found in raw/, skipping")
            continue
        prefix = vid_name.replace(".mp4", "").replace(" ", "_")[:30] + f"_{split_name}"
        frames = extract_frames(vid_path, images_dir, pos_interval, prefix)
        all_pos_frames.extend(frames)
        # Write empty label files (annotations needed separately)
        for frame_path in frames:
            label_path = labels_dir / (frame_path.stem + ".txt")
            if not label_path.exists():
                label_path.touch()  # Placeholder — needs annotation tool

    for vid_name in neg_videos:
        vid_path = HN_DIR / vid_name
        if not vid_path.exists():
            print(f"  WARNING: {vid_name} not found in hard_negatives/, skipping")
            continue
        prefix = vid_name.replace(".mp4", "").replace(" ", "_")[:30] + f"_{split_name}_neg"
        frames = extract_frames(vid_path, negs_dir, neg_interval, prefix)
        # Hard negatives get empty label files (no waterlogging = no annotations)
        for frame_path in frames:
            neg_labels_dir = DATASET_DIR / "labels" / f"{split_name}_negatives"
            neg_labels_dir.mkdir(parents=True, exist_ok=True)
            label_path = neg_labels_dir / (frame_path.stem + ".txt")
            if not label_path.exists():
                label_path.touch()  # Empty = no waterlogging annotation

    return len(all_pos_frames)


def main():
    # Clean previous v2 dataset if exists
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    DATASET_DIR.mkdir(parents=True)

    train_count = build_split("train", TRAIN_POSITIVES, TRAIN_NEGATIVES, POSITIVE_INTERVAL, NEGATIVE_INTERVAL)
    val_count   = build_split("val",   VAL_POSITIVES,   VAL_NEGATIVES,   POSITIVE_INTERVAL, NEGATIVE_INTERVAL)
    test_count  = build_split("test",  TEST_POSITIVES,  [],              POSITIVE_INTERVAL, NEGATIVE_INTERVAL)

    # Write corrected data.yaml (Step 17)
    data_yaml = DATASET_DIR / "data.yaml"
    yaml_content = f"""# Waterlogging Dataset V2 — Phase 10 Step 17 Corrected Split
# CRITICAL FIX: V1 had train == val (same files). This version uses VIDEO-LEVEL split.
#
# TRAIN positives: {', '.join(TRAIN_POSITIVES)}
# VAL positives:   {', '.join(VAL_POSITIVES)}
# TEST positives:  {', '.join(TEST_POSITIVES)} (held out — NOT used during training or threshold tuning)
#
# Negatives included in train_negatives/ and val_negatives/ directories.
# Integrate negatives: run scripts/merge_negatives_into_splits.py after annotation.

path: {DATASET_DIR}
train: images/train
val:   images/val
test:  images/test

names:
  0: waterlogging

# IMPORTANT: Annotation required before training!
# Positive frames have EMPTY placeholder label files.
# Annotate using: labelImg, CVAT, or Roboflow on images/train/ and images/val/
# After annotation, merge negatives:
#   - Copy images/train_negatives/ frames into images/train/
#   - Copy labels/train_negatives/ (empty files) into labels/train/
"""
    data_yaml.write_text(yaml_content)

    # Write metadata JSON
    manifest = {
        "version": "v2",
        "phase10_step": "17 - Corrected video-level train/val/test split",
        "split": {
            "train_positives": TRAIN_POSITIVES,
            "val_positives": VAL_POSITIVES,
            "test_positives": TEST_POSITIVES,
            "train_negatives": TRAIN_NEGATIVES,
            "val_negatives": VAL_NEGATIVES,
        },
        "frame_counts": {
            "train_positive_frames": train_count,
            "val_positive_frames": val_count,
            "test_positive_frames": test_count,
        },
        "annotation_status": "PENDING — label files are empty placeholders",
        "data_yaml": str(data_yaml),
        "critical_fix": "V1 data.yaml had train == val (identical files). All val metrics in V1 were measuring memorization. V2 uses video-level split for genuine generalization measurement.",
    }
    manifest_path = DATASET_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "="*60)
    print("DATASET V2 BUILD COMPLETE")
    print("="*60)
    print(f"Location: {DATASET_DIR}")
    print(f"Train positive frames: {train_count}")
    print(f"Val positive frames:   {val_count}")
    print(f"Test positive frames:  {test_count} (HELD OUT — do not annotate until final eval)")
    print(f"data.yaml: {data_yaml}")
    print()
    print("NEXT STEP: Annotate images/train/ and images/val/ with waterlogging masks")
    print("  Recommended tool: labelImg (YOLO segmentation mode)")
    print("  Or: Upload to Roboflow / CVAT for team annotation")
    print()
    print("After annotation, run: python3 backend/ai/waterlogging/retrain_v2.py")


if __name__ == "__main__":
    main()
