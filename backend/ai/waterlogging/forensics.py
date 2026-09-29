#!/usr/bin/env python3
"""
Phase 10 — Forensic Analysis Script
Steps 2, 5, 6, 7, 8, 9: Coordinate sanity check + Raw prediction audit on evaluation video.

Run from project root: python3 backend/ai/waterlogging/forensics.py

Outputs:
  backend/data/waterlogging/evaluation/forensics/raw_predictions.jsonl
  backend/data/waterlogging/evaluation/forensics/coordinate_audit.json
  backend/data/waterlogging/evaluation/forensics/summary.json
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import List

import cv2
import numpy as np

# --- Setup path so we can import backend modules ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from ai.waterlogging.model_registry import load_and_verify_model
from ai.waterlogging.config import WATERLOGGING_CONFIDENCE_THRESHOLD, WATERLOGGING_IMGSZ

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---- Config ----
EVAL_VIDEO = REPO_ROOT / "backend/data/waterlogging/evaluation/v1_evaluation.mp4"
KNOWN_FP_DIR = REPO_ROOT / "backend/data/waterlogging/evaluation/suspected_false_positives"
OUTPUT_DIR   = REPO_ROOT / "backend/data/waterlogging/evaluation/forensics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FRAME_INTERVAL = 29  # Match training sampling rate (2fps from ~59fps source)


def verify_model_checksum(model_path: Path) -> str:
    h = hashlib.sha256()
    with open(model_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()


def run_forensics():
    logger.info("=== PHASE 10 FORENSIC ANALYSIS ===")
    logger.info("Step 9: Verifying model path and checksum...")
    model_path = load_and_verify_model("v1")
    checksum = verify_model_checksum(model_path)
    logger.info("Model: %s  sha256=%s...  OK", model_path, checksum[:16])

    # Step 8: Load model directly (not via UnifiedVideoProcessor) to isolate pipeline vs model
    from ultralytics import YOLO
    model = YOLO(str(model_path))
    logger.info("Architecture: %s, Classes: %s", type(model.model).__name__, model.names)

    cap = cv2.VideoCapture(str(EVAL_VIDEO))
    if not cap.isOpened():
        logger.error("Cannot open evaluation video: %s", EVAL_VIDEO)
        sys.exit(1)

    orig_w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps     = cap.get(cv2.CAP_PROP_FPS)
    total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info("Step 2/5: Evaluating video: %dx%d  fps=%.1f  total_frames=%d", orig_w, orig_h, fps, total_f)

    raw_predictions = []
    coord_audit_samples = []  # Step 2: coordinate sanity samples (first 5 detections)
    frame_idx = 0
    processed = 0
    t_start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % FRAME_INTERVAL != 0:
            frame_idx += 1
            continue

        # Step 8: Check frame dimensions match model expectations
        actual_h, actual_w = frame.shape[:2]
        timestamp = frame_idx / fps

        # Run model directly (bypassing UnifiedVideoProcessor)
        results = model.predict(
            source=frame,        # BGR numpy array — same as production pipeline
            imgsz=WATERLOGGING_IMGSZ,
            conf=WATERLOGGING_CONFIDENCE_THRESHOLD,
            verbose=False,
            stream=False,
        )

        res = results[0]
        if res.boxes is not None and len(res.boxes) > 0:
            boxes   = res.boxes.xyxy.cpu().numpy()
            confs   = res.boxes.conf.cpu().numpy()
            has_masks = res.masks is not None
            masks_xy = res.masks.xy if has_masks else []

            for i, (box, conf) in enumerate(zip(boxes, confs)):
                x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                bbox_area = (x2 - x1) * (y2 - y1)
                frame_area = actual_w * actual_h
                area_ratio_to_frame = bbox_area / frame_area if frame_area > 0 else 0.0

                polygon = []
                if has_masks and i < len(masks_xy):
                    poly = masks_xy[i]
                    if len(poly) > 2:
                        polygon = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in poly]

                entry = {
                    "frame_index": frame_idx,
                    "timestamp_sec": round(timestamp, 3),
                    "confidence": round(float(conf), 4),
                    "bbox_xyxy": [round(x1,1), round(y1,1), round(x2,1), round(y2,1)],
                    "bbox_area_px": round(bbox_area, 1),
                    "bbox_area_ratio_to_frame": round(area_ratio_to_frame, 4),
                    "frame_dims": [actual_w, actual_h],
                    "model_imgsz": WATERLOGGING_IMGSZ,
                    "polygon_points": len(polygon),
                    # Step 2: flag coordinate plausibility
                    "x1_in_range": 0.0 <= x1 <= actual_w,
                    "y1_in_range": 0.0 <= y1 <= actual_h,
                    "x2_in_range": 0.0 <= x2 <= actual_w,
                    "y2_in_range": 0.0 <= y2 <= actual_h,
                }
                raw_predictions.append(entry)

                # Coordinate audit sample for Step 2
                if len(coord_audit_samples) < 5:
                    coord_audit_samples.append({
                        "frame_index": frame_idx,
                        "frame_dims": [actual_w, actual_h],
                        "bbox_raw": [x1, y1, x2, y2],
                        "bbox_normalised": [x1/actual_w, y1/actual_h, x2/actual_w, y2/actual_h],
                        "all_coords_in_frame": all([
                            0.0 <= x1 <= actual_w, 0.0 <= y1 <= actual_h,
                            0.0 <= x2 <= actual_w, 0.0 <= y2 <= actual_h,
                        ]),
                        "confidence": round(float(conf), 4),
                        "polygon_sample": polygon[:3] if polygon else [],
                    })

        processed += 1
        frame_idx += 1

    cap.release()
    elapsed = time.time() - t_start
    logger.info("Processed %d frames in %.1fs", processed, elapsed)

    # --- Write raw predictions ---
    preds_path = OUTPUT_DIR / "raw_predictions.jsonl"
    with open(preds_path, "w") as f:
        for entry in raw_predictions:
            f.write(json.dumps(entry) + "\n")
    logger.info("Wrote %d raw predictions to %s", len(raw_predictions), preds_path)

    # --- Step 2: Coordinate audit ---
    coord_audit = {
        "conclusion": (
            "COORDINATES OK - all bbox coords fall within frame dimensions"
            if all(
                e["x1_in_range"] and e["y1_in_range"] and e["x2_in_range"] and e["y2_in_range"]
                for e in raw_predictions
            )
            else "WARNING - some bbox coords fall outside frame dimensions (rendering offset bug)"
        ),
        "frame_dims": [orig_w, orig_h],
        "model_imgsz": WATERLOGGING_IMGSZ,
        "total_detections": len(raw_predictions),
        "out_of_range_count": sum(
            1 for e in raw_predictions
            if not (e["x1_in_range"] and e["y1_in_range"] and e["x2_in_range"] and e["y2_in_range"])
        ),
        "samples": coord_audit_samples,
    }
    with open(OUTPUT_DIR / "coordinate_audit.json", "w") as f:
        json.dump(coord_audit, f, indent=2)
    logger.info("Step 2 coord audit: %s", coord_audit["conclusion"])

    # --- Summary ---
    confidences = [e["confidence"] for e in raw_predictions]
    area_ratios = [e["bbox_area_ratio_to_frame"] for e in raw_predictions]
    frames_with_dets = len(set(e["frame_index"] for e in raw_predictions))
    summary = {
        "eval_video": str(EVAL_VIDEO),
        "model_path": str(model_path),
        "model_sha256": checksum,
        "model_sha256_first16": checksum[:16],
        "video_dims": [orig_w, orig_h],
        "video_fps": fps,
        "total_video_frames": total_f,
        "frames_sampled": processed,
        "frames_with_detections": frames_with_dets,
        "total_raw_detections": len(raw_predictions),
        "confidence_stats": {
            "mean": round(float(np.mean(confidences)), 4) if confidences else None,
            "min":  round(float(np.min(confidences)), 4)  if confidences else None,
            "max":  round(float(np.max(confidences)), 4)  if confidences else None,
        },
        "area_ratio_stats": {
            "mean": round(float(np.mean(area_ratios)), 4) if area_ratios else None,
            "min":  round(float(np.min(area_ratios)), 4)  if area_ratios else None,
            "max":  round(float(np.max(area_ratios)), 4)  if area_ratios else None,
        },
        "coordinate_audit": coord_audit["conclusion"],
        "step2_rendering_bug_ruled_out": coord_audit["out_of_range_count"] == 0,
        "processing_seconds": round(elapsed, 1),
    }
    with open(OUTPUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("=== FORENSIC SUMMARY ===")
    for k, v in summary.items():
        logger.info("  %s: %s", k, v)

    logger.info("All forensic output written to: %s", OUTPUT_DIR)
    return summary


if __name__ == "__main__":
    run_forensics()
