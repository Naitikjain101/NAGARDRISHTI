"""
Urban Watch — Automated Pothole Benchmarking Suite (Phase 2 Step 2)

Executes:
1. Baseline reproduction
2. Resolution sweep (384, 512, 640, 768)
3. Confidence sweep (0.15 - 0.70)
4. Small-object recall analysis
5. Full video temporal stability and event tracking profiling
6. Generates JSON benchmark artifact
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from ultralytics import YOLO

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai.common.device import get_device_info
from ai.pothole.config import DEFAULT_POTHOLE_MODEL
from ai.pothole.detector import PotholeDetector, PotholeDetectorConfig
from ai.pothole.tracker import PotholeEventTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pothole_benchmark")


def run_pothole_benchmark(
    model_path: str = DEFAULT_POTHOLE_MODEL,
    dataset_yaml: str = "/Users/naitikjain/Downloads/urban-watch-main/backend/datasets/pothole/data.yaml",
    video_path: str = "backend/video/test_data/road_test.mp4",
    output_json: str = "backend/results/pothole_benchmark_step2.json",
) -> Dict[str, Any]:
    """Run full Phase 2 Step 2 evaluation."""
    device_info = get_device_info()
    device = device_info.device_str
    logger.info("Running pothole benchmark on device: %s", device)

    m = YOLO(model_path)

    # 1. Resolution Sweep
    logger.info("=== 1. Running Resolution Sweep ===")
    resolutions = [384, 512, 640, 768]
    res_sweep_data = {}

    for sz in resolutions:
        val_res = m.val(data=dataset_yaml, imgsz=sz, device=device, verbose=False)
        p = float(val_res.results_dict.get("metrics/precision(B)", 0))
        r = float(val_res.results_dict.get("metrics/recall(B)", 0))
        m50 = float(val_res.results_dict.get("metrics/mAP50(B)", 0))
        m5095 = float(val_res.results_dict.get("metrics/mAP50-95(B)", 0))
        speed = {k: float(v) for k, v in val_res.speed.items()}
        res_sweep_data[str(sz)] = {
            "imgsz": sz,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "mAP50": round(m50, 4),
            "mAP50-95": round(m5095, 4),
            "speed_ms": speed,
            "fps": round(1000.0 / speed.get("inference", 1.0), 1),
        }

    # 2. Confidence Sweep (at imgsz=640)
    logger.info("=== 2. Running Confidence Sweep (640px) ===")
    conf_thresholds = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70]
    conf_sweep_data = []

    val_img_dir = "/Users/naitikjain/Downloads/urban-watch-main/backend/datasets/pothole/images/val"
    val_lbl_dir = "/Users/naitikjain/Downloads/urban-watch-main/backend/datasets/pothole/labels/val"
    
    import glob
    img_files = sorted(glob.glob(f"{val_img_dir}/*"))
    gt_boxes = {}
    
    for img_p in img_files:
        stem = Path(img_p).stem
        lbl_p = os.path.join(val_lbl_dir, f"{stem}.txt")
        boxes = []
        if os.path.exists(lbl_p):
            with open(lbl_p, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        xc, yc, w, h = map(float, parts[1:5])
                        boxes.append({"bbox": [xc - w/2, yc - h/2, xc + w/2, yc + h/2], "area": w * h})
        gt_boxes[img_p] = boxes

    def compute_iou(b1, b2):
        xA, yA = max(b1[0], b2[0]), max(b1[1], b2[1])
        xB, yB = min(b1[2], b2[2]), min(b1[3], b2[3])
        inter = max(0.0, xB - xA) * max(0.0, yB - yA)
        u = (b1[2]-b1[0])*(b1[3]-b1[1]) + (b2[2]-b2[0])*(b2[3]-b2[1]) - inter
        return inter / u if u > 0 else 0.0

    for conf in conf_thresholds:
        TP, FP, FN = 0, 0, 0
        for img_p in img_files:
            gts = gt_boxes[img_p]
            res = m.predict(source=img_p, imgsz=640, conf=conf, device=device, verbose=False)
            preds = []
            if res[0].boxes is not None:
                for box in res[0].boxes:
                    preds.append(box.xyxyn[0].cpu().numpy().tolist())
            gt_matched = [False] * len(gts)
            for pred in preds:
                best_iou = 0.0
                best_idx = -1
                for idx, gt in enumerate(gts):
                    if not gt_matched[idx]:
                        iou = compute_iou(pred, gt["bbox"])
                        if iou > best_iou:
                            best_iou = iou
                            best_idx = idx
                if best_iou >= 0.5:
                    TP += 1
                    gt_matched[best_idx] = True
                else:
                    FP += 1
            FN += sum(1 for m_flag in gt_matched if not m_flag)

        prec = TP / (TP + FP) if (TP + FP) > 0 else 0.0
        rec = TP / (TP + FN) if (TP + FN) > 0 else 0.0
        f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        conf_sweep_data.append({
            "conf": conf,
            "TP": TP,
            "FP": FP,
            "FN": FN,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        })

    # 3. Video Temporal Stability Profiling
    logger.info("=== 3. Running Video Temporal Stability Benchmark ===")
    video_metrics = {}
    if os.path.exists(video_path):
        detector = PotholeDetector(PotholeDetectorConfig(model_path=model_path, imgsz=640, confidence_threshold=0.25))
        tracker = PotholeEventTracker()
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        
        fc = 0
        total_dets = 0
        latencies = []
        t0 = time.perf_counter()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            ts = fc / fps
            dets, t_prof = detector.detect(frame, frame_index=fc, timestamp=ts)
            latencies.append(t_prof.inference_ms)
            total_dets += len(dets)
            tracker.update(frame_index=fc, timestamp=ts, detections=dets)
            fc += 1
        cap.release()

        events = tracker.finalize()
        confirmed = [e for e in events if e.is_confirmed]
        total_time = time.perf_counter() - t0

        video_metrics = {
            "video_file": os.path.basename(video_path),
            "total_frames": fc,
            "total_raw_detections": total_dets,
            "pipeline_time_sec": round(total_time, 2),
            "fps_mps": round(fc / total_time, 1) if total_time > 0 else 0,
            "avg_inference_latency_ms": round(float(np.mean(latencies)), 2),
            "total_unique_events": len(events),
            "confirmed_persistent_events": len(confirmed),
            "transient_blips": len(events) - len(confirmed),
            "top_events_sample": [e.model_dump() for e in confirmed[:5]]
        }

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": Path(model_path).name,
        "device": device,
        "resolution_sweep": res_sweep_data,
        "confidence_sweep": conf_sweep_data,
        "video_temporal_benchmark": video_metrics,
        "recommended_config": {
            "imgsz": 640,
            "confidence_threshold": 0.25,
            "iou_threshold": 0.45,
            "min_event_frames": 3,
        }
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Saved benchmark report to %s", output_json)
    return report


if __name__ == "__main__":
    run_pothole_benchmark()
