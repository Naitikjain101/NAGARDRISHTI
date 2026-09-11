import os
import cv2
import json
import time
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict

from ai.waterlogging.detector import WaterloggingDetector, WaterloggingDetectorConfig
from ai.unified.events import WaterloggingEventEngine

from ai.waterlogging.config import DEFAULT_WATERLOGGING_MODEL

EVAL_DIR = Path("backend/data/waterlogging/evaluation")
FP_DIR = EVAL_DIR / "suspected_false_positives"
METADATA_DIR = Path("backend/data/waterlogging/metadata")
YOLO_DIR = Path("backend/data/waterlogging/yolo_dataset")
RESULTS_CSV = Path("runs/segment/models/waterlogging/v1/results.csv")
VIDEO_PATH = Path("backend/data/waterlogging/raw/17929886-uhd_3840_2160_59fps_compressed.mp4")

# Tracker will be initialized inside run_validation

@dataclass
class ValidationMetrics:
    total_frames: int = 0
    processed_frames: int = 0
    total_raw_detections: int = 0
    total_validated_events: int = 0
    total_processing_time: float = 0.0
    total_inference_time: float = 0.0
    
    # GT Match
    gt_frames_evaluated: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    # Confidence and Area
    sum_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0
    sum_area_ratio: float = 0.0
    max_area_ratio: float = 0.0

metrics = ValidationMetrics()

def compute_iou(poly1, poly2, width, height):
    """Computes approximate IoU of two polygons using a discrete mask."""
    # Create empty masks
    mask1 = np.zeros((height, width), dtype=np.uint8)
    mask2 = np.zeros((height, width), dtype=np.uint8)
    
    # Convert normalized polygons to pixel coordinates
    pts1 = np.array([[int(p[0] * width), int(p[1] * height)] for p in poly1], np.int32)
    pts2 = np.array([[int(p[0] * width), int(p[1] * height)] for p in poly2], np.int32)
    
    if len(pts1) < 3 or len(pts2) < 3:
        return 0.0
        
    cv2.fillPoly(mask1, [pts1], 1)
    cv2.fillPoly(mask2, [pts2], 1)
    
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    
    if union == 0:
        return 0.0
    return intersection / union

def get_training_metrics():
    if not RESULTS_CSV.exists():
        return {}
    
    try:
        df = pd.read_csv(RESULTS_CSV)
        # Clean column names (YOLO often has leading spaces)
        df.columns = [c.strip() for c in df.columns]
        
        last_row = df.iloc[-1]
        
        metrics = {
            "epoch": int(last_row.get("epoch", 0)),
            "box_loss": float(last_row.get("train/box_loss", 0.0)),
            "seg_loss": float(last_row.get("train/seg_loss", 0.0)),
            "cls_loss": float(last_row.get("train/cls_loss", 0.0)),
            "val_box_loss": float(last_row.get("val/box_loss", 0.0)),
            "val_seg_loss": float(last_row.get("val/seg_loss", 0.0)),
            "map50_box": float(last_row.get("metrics/mAP50(B)", 0.0)),
            "map50_95_box": float(last_row.get("metrics/mAP50-95(B)", 0.0)),
            "map50_mask": float(last_row.get("metrics/mAP50(M)", 0.0)),
            "map50_95_mask": float(last_row.get("metrics/mAP50-95(M)", 0.0))
        }
        return metrics
    except Exception as e:
        print(f"Error reading results.csv: {e}")
        return {}

def run_validation():
    os.makedirs(EVAL_DIR, exist_ok=True)
    os.makedirs(FP_DIR, exist_ok=True)
    
    # 1. Dataset Audit
    num_train_images = len(list((YOLO_DIR / "images/annotation_pool").glob("*.jpg")))
    
    # Load GT metadata
    gt_data = {}
    for meta_file in METADATA_DIR.glob("*.json"):
        with open(meta_file, "r") as f:
            data = json.load(f)
            # Only use ANNOTATED or NO_WATERLOGGING frames as GT
            if data.get("annotation_status") in ["ANNOTATED", "NO_WATERLOGGING"]:
                img_name = meta_file.name.replace(".json", ".jpg")
                gt_data[img_name] = data
                
    dataset_audit = {
        "total_annotated_frames": len(gt_data),
        "total_yolo_images": num_train_images,
        "single_source_leakage": "Single-source frame split — generalization not established." if len(gt_data) > 0 else "Unknown"
    }

    # 2. Setup Video and Detector
    config = WaterloggingDetectorConfig(
        model_path=DEFAULT_WATERLOGGING_MODEL,
        imgsz=640,
        confidence_threshold=0.40
    )
    detector = WaterloggingDetector(config)
    detector.load()
    
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        print(f"Error opening video: {VIDEO_PATH}")
        return
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    metrics.total_frames = total_frames
    
    # We will create an internal tracker for temporal stability forensics
    tracker = WaterloggingEventEngine(frame_width=width, frame_height=height)
    
    out_video_path = EVAL_DIR / "v1_evaluation.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(out_video_path), fourcc, fps, (width, height))
    
    frame_idx = 0
    t_start_total = time.perf_counter()
    
    # For temporal stability
    active_events = {}
    historical_events = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_name = f"frame_{frame_idx:06d}.jpg"
        has_gt = frame_name in gt_data
        
        t0 = time.perf_counter()
        detections, frame_timer = detector.detect(frame, frame_idx, frame_idx/fps)
        metrics.total_inference_time += frame_timer.inference_ms / 1000.0
        
        # Temporal Validation
        _ = tracker.update(frame_idx, frame_idx/fps, detections, [])
        valid_events = tracker.get_unified_events()
        
        metrics.total_raw_detections += len(detections)
        metrics.total_validated_events += len(valid_events)
        
        # Draw on frame
        display_frame = frame.copy()
        
        # Draw Raw Detections (thin red)
        for d in detections:
            metrics.sum_confidence += d.confidence
            metrics.min_confidence = min(metrics.min_confidence, d.confidence)
            metrics.max_confidence = max(metrics.max_confidence, d.confidence)
            metrics.sum_area_ratio += d.area_ratio
            metrics.max_area_ratio = max(metrics.max_area_ratio, d.area_ratio)
            
            pts = np.array([[int(p[0] * width), int(p[1] * height)] for p in d.polygon], np.int32)
            if len(pts) > 2:
                cv2.polylines(display_frame, [pts], True, (0, 0, 255), 1)
                # Label
                label = f"Raw: {d.confidence:.2f}"
                cv2.putText(display_frame, label, (int(d.bbox[0]), int(d.bbox[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                
            # Suspicious FP logic
            # If no GT, check if extremely huge (e.g. > 60% of frame) or very thin
            if not has_gt and d.area_ratio > 0.6:
                cv2.imwrite(str(FP_DIR / f"fp_large_{frame_name}"), frame)
                
        # Draw Validated Events (thick green, fill)
        model_polys = []
        for e in valid_events:
            d_poly = e.last_polygon
            d_bbox = e.representative_bbox
            d_conf = e.max_confidence
            
            model_polys.append(d_poly)
            
            pts = np.array([[int(p[0] * width), int(p[1] * height)] for p in d_poly], np.int32)
            if len(pts) > 2:
                # Fill
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [pts], (0, 255, 0))
                cv2.addWeighted(overlay, 0.4, display_frame, 0.6, 0, display_frame)
                # Border
                cv2.polylines(display_frame, [pts], True, (0, 255, 0), 2)
                
                # Text
                label = f"WATERLOGGING\nConf: {d_conf:.2f}\nValidated Event"
                y0, dy = int(d_bbox[1]), 20
                for i, line in enumerate(label.split('\n')):
                    y = y0 - (2 - i) * dy
                    cv2.putText(display_frame, line, (int(d_bbox[0]), max(20, y)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
            # Temporal tracking stats
            if e.event_id not in active_events:
                active_events[e.event_id] = {"start": frame_idx, "frames": 1, "max_conf": d_conf}
            else:
                active_events[e.event_id]["frames"] += 1
                active_events[e.event_id]["max_conf"] = max(active_events[e.event_id]["max_conf"], d_conf)
                active_events[e.event_id]["end"] = frame_idx
                
        # GT Comparison
        if has_gt:
            metrics.gt_frames_evaluated += 1
            gt_polys = [ann.get("polygon", []) for ann in gt_data[frame_name].get("annotations", [])]
            gt_polys = [p for p in gt_polys if len(p) >= 3]
            
            if len(gt_polys) == 0 and len(valid_events) > 0:
                metrics.false_positives += 1
                cv2.imwrite(str(FP_DIR / f"fp_gt_{frame_name}"), display_frame)
            elif len(gt_polys) > 0 and len(valid_events) == 0:
                metrics.false_negatives += 1
            elif len(gt_polys) > 0 and len(valid_events) > 0:
                # Simplified TP if any overlap exists
                max_iou = 0.0
                for mp in model_polys:
                    for gp in gt_polys:
                        iou = compute_iou(mp, gp, width, height)
                        max_iou = max(max_iou, iou)
                if max_iou > 0.1:
                    metrics.true_positives += 1
                else:
                    metrics.false_positives += 1
                    cv2.imwrite(str(FP_DIR / f"fp_iou_{frame_name}"), display_frame)
                    
        out.write(display_frame)
        frame_idx += 1
        metrics.processed_frames += 1
        
        # Check active events for expiration (simplified for historical tracking)
        expired = []
        for eid, stats in active_events.items():
            if frame_idx - stats.get("end", stats["start"]) > 10:
                historical_events.append(stats)
                expired.append(eid)
        for eid in expired:
            del active_events[eid]
            
        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx}/{total_frames}")

    # Cleanup
    for stats in active_events.values():
        historical_events.append(stats)
        
    cap.release()
    out.release()
    metrics.total_processing_time = time.perf_counter() - t_start_total
    
    # 3. Output Reports
    generate_reports(dataset_audit, historical_events)


def generate_reports(dataset_audit, historical_events):
    train_metrics = get_training_metrics()
    
    # Calculate derived
    avg_conf = metrics.sum_confidence / max(1, metrics.total_raw_detections)
    avg_area = metrics.sum_area_ratio / max(1, metrics.total_raw_detections)
    fps = metrics.processed_frames / max(0.001, metrics.total_processing_time)
    inf_fps = metrics.processed_frames / max(0.001, metrics.total_inference_time)
    
    precision = metrics.true_positives / max(1, metrics.true_positives + metrics.false_positives)
    recall = metrics.true_positives / max(1, metrics.true_positives + metrics.false_negatives)
    
    stable = len([e for e in historical_events if e["frames"] > 30])
    intermittent = len([e for e in historical_events if 5 < e["frames"] <= 30])
    fragments = len([e for e in historical_events if e["frames"] <= 5])
    
    # Determine Production Status
    map50 = train_metrics.get("map50_mask", 0.0)
    generalization = dataset_audit["single_source_leakage"]
    status = "NOT READY"
    if precision > 0.8 and recall > 0.8 and map50 > 0.7 and "Single-source" not in generalization:
        status = "READY"
        
    report_md = f"""# Waterlogging V1 — Forensic Validation Report

## MODEL
Path: `runs/segment/models/waterlogging/v1/weights/best.pt`

## DATASET
{dataset_audit['total_yolo_images']} total images. 
{dataset_audit['single_source_leakage']}

## TRAINING INFORMATION
- mAP50 (Box): {train_metrics.get('map50_box', 0):.4f}
- mAP50-95 (Box): {train_metrics.get('map50_95_box', 0):.4f}
- mAP50 (Mask): {train_metrics.get('map50_mask', 0):.4f}
- mAP50-95 (Mask): {train_metrics.get('map50_95_mask', 0):.4f}
- Box Loss: {train_metrics.get('val_box_loss', 0):.4f}
- Seg Loss: {train_metrics.get('val_seg_loss', 0):.4f}

## PERFORMANCE
- Total Processing Time: {metrics.total_processing_time:.2f}s
- Overall FPS: {fps:.2f}
- Inference FPS: {inf_fps:.2f}
- Total Frames: {metrics.processed_frames}

## DETECTION STATISTICS
- Raw Detections: {metrics.total_raw_detections}
- Validated Events: {metrics.total_validated_events}
- Avg Confidence: {avg_conf:.2f} (Min: {metrics.min_confidence:.2f}, Max: {metrics.max_confidence:.2f})
- Avg Area Ratio: {avg_area:.3f} (Max: {metrics.max_area_ratio:.3f})

## GT COMPARISON (On {metrics.gt_frames_evaluated} annotated frames)
- True Positives: {metrics.true_positives}
- False Positives: {metrics.false_positives}
- False Negatives: {metrics.false_negatives}
- Precision: {precision:.2f}
- Recall: {recall:.2f}

## TEMPORAL STABILITY
- Stable Events (>30 frames): {stable}
- Intermittent (6-30 frames): {intermittent}
- Fragmented/One-off (<=5 frames): {fragments}

## WATERLOGGING V1 VERDICT

Model: V1 Segmentation
Dataset: {dataset_audit['total_yolo_images']} images
Source Video: 17929886-uhd_3840_2160_59fps_compressed.mp4

Precision: {precision:.2f}
Recall: {recall:.2f}
mAP50: {train_metrics.get('map50_mask', 0):.4f}
mAP50-95: {train_metrics.get('map50_95_mask', 0):.4f}

Inference FPS: {inf_fps:.2f}
Average latency: {(metrics.total_inference_time/max(1, metrics.processed_frames))*1000:.2f} ms

Raw detections: {metrics.total_raw_detections}
Validated events: {metrics.total_validated_events}

False positives: {metrics.false_positives}
False negatives: {metrics.false_negatives}

Temporal stability: {stable} stable, {intermittent} intermittent, {fragments} fragmented

Dataset limitations: Single-source video limits environmental variance.

GENERALIZATION:
[NOT ESTABLISHED] (Single source video)

PRODUCTION STATUS:
[{status}]

Recommendation for V2: 
Collect frames from different environments, lighting conditions, and camera angles. Hard-negative mining on dry reflective roads is required.
"""
    
    with open(EVAL_DIR / "v1_validation_report.md", "w") as f:
        f.write(report_md)
        
    metrics_json = {
        "precision": precision,
        "recall": recall,
        "map50": train_metrics.get("map50_mask", 0.0),
        "fps": fps,
        "raw_detections": metrics.total_raw_detections,
        "validated_events": metrics.total_validated_events
    }
    with open(EVAL_DIR / "v1_metrics.json", "w") as f:
        json.dump(metrics_json, f, indent=2)
        
    print("Forensic validation complete!")
    print(f"Report saved to {EVAL_DIR / 'v1_validation_report.md'}")

if __name__ == "__main__":
    run_validation()
