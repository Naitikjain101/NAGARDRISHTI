import sys
import time
import json
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np
import torch
from ultralytics import YOLO

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))
from ai.common.config import CONFIDENCE_THRESHOLD, INFERENCE_IMGSZ
from ai.common.device import get_device_info
from ai.detection.classes import get_phase1_class_ids, is_vehicle_class
from ai.detection.vehicle_suppression import VehicleDuplicateSuppressor
from ai.tracking.tracker import ByteTracker, TrackerArgs, stabilize_class
from ai.traffic.vehicle_counter import VehicleCounter

VIDEO_PATH = "/Users/naitikjain/Downloads/Nagar drishti/traffic_test-2-2-2.mp4"
MAX_FRAMES = 300

def run_precision_regression_benchmark():
    device_info = get_device_info()
    device = device_info.device_str
    print(f"=== Urban Watch Precision Regression Benchmark ===")
    print(f"Device: {device} ({device_info.device_name})")
    print(f"Video: {VIDEO_PATH}")
    print(f"Frames: {MAX_FRAMES} | Imgsz: {INFERENCE_IMGSZ} | Conf: {CONFIDENCE_THRESHOLD}")
    
    # -------------------------------------------------------------------------
    # 1. Benchmark BEFORE (Raw YOLOv8n + Raw ByteTrack)
    # -------------------------------------------------------------------------
    print("\n[1/2] Running BEFORE (Raw YOLOv8n @ conf 0.30)...")
    model_before = YOLO("yolov8n.pt")
    model_before.to(device)
    class_filter = get_phase1_class_ids(model_before.names)
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_idx = 0
    t_start = time.perf_counter()
    
    raw_counter = VehicleCounter()
    raw_total_dets = 0
    raw_class_flickers = 0
    raw_tracks_created = 0
    raw_track_history = defaultdict(list)
    
    # Standard raw ByteTracker without suppression or stabilization
    from ultralytics.trackers.byte_tracker import BYTETracker
    raw_byte_tracker = BYTETracker(TrackerArgs(), frame_rate=30)
    
    while frame_idx < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
            
        h, w = frame.shape[:2]
        res = model_before.predict(
            source=frame,
            imgsz=INFERENCE_IMGSZ,
            conf=CONFIDENCE_THRESHOLD,
            classes=class_filter,
            device=device,
            verbose=False
        )[0]
        
        boxes_obj = res.boxes
        if boxes_obj is not None:
            raw_total_dets += len(boxes_obj)
            t_out = raw_byte_tracker.update(boxes_obj.cpu())
        else:
            from ultralytics.engine.results import Boxes
            empty = Boxes(torch.zeros((0, 6)), (h, w))
            t_out = raw_byte_tracker.update(empty)
            
        from ai.common.schemas import TrackResult
        frame_tracks = []
        if t_out is not None and len(t_out) > 0:
            for row in t_out:
                t_id = int(row[4])
                c_id = int(row[6])
                c_name = model_before.names.get(c_id, f"class_{c_id}")
                cf = float(row[5])
                
                # Check flicker
                if t_id in raw_track_history and raw_track_history[t_id][-1] != c_name:
                    raw_class_flickers += 1
                raw_track_history[t_id].append(c_name)
                
                frame_tracks.append(
                    TrackResult(
                        track_id=t_id,
                        class_id=c_id,
                        class_name=c_name,
                        confidence=cf,
                        bbox=[float(row[0]), float(row[1]), float(row[2]), float(row[3])],
                        first_seen_timestamp=frame_idx / 30.0,
                        last_seen_timestamp=frame_idx / 30.0,
                        frames_seen=len(raw_track_history[t_id])
                    )
                )
        raw_counter.update(frame_tracks)
        frame_idx += 1
        
    cap.release()
    t_elapsed_before = time.perf_counter() - t_start
    fps_before = frame_idx / t_elapsed_before if t_elapsed_before > 0 else 0
    summary_before = raw_counter.get_summary()
    
    before_results = {
        "fps": round(fps_before, 2),
        "total_frames": frame_idx,
        "raw_detections": raw_total_dets,
        "avg_detections_per_frame": round(raw_total_dets / frame_idx, 2),
        "unique_vehicles_counted": summary_before.total_unique_vehicles,
        "by_class_counts": summary_before.by_class,
        "raw_class_flickers": raw_class_flickers,
        "total_unique_tracks": len(raw_track_history)
    }
    
    # -------------------------------------------------------------------------
    # 2. Benchmark AFTER (YOLOv8n + Smart Duplicate Suppression + Temporal Stabilization)
    # -------------------------------------------------------------------------
    print("\n[2/2] Running AFTER (YOLOv8n @ conf 0.30 + Smart Suppression + Temporal Stabilization)...")
    model_after = YOLO("yolov8n.pt")
    model_after.to(device)
    
    tracker_after = ByteTracker(model=model_after, device=device)
    after_counter = VehicleCounter()
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_idx = 0
    t_start = time.perf_counter()
    
    while frame_idx < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
            
        tracks, _ = tracker_after.update(
            frame=frame,
            frame_index=frame_idx,
            timestamp=frame_idx / 30.0,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            imgsz=INFERENCE_IMGSZ,
            class_filter=class_filter
        )
        after_counter.update(tracks)
        frame_idx += 1
        
    cap.release()
    t_elapsed_after = time.perf_counter() - t_start
    fps_after = frame_idx / t_elapsed_after if t_elapsed_after > 0 else 0
    summary_after = after_counter.get_summary()
    quality = tracker_after.get_quality_metrics()
    
    after_results = {
        "fps": round(fps_after, 2),
        "total_frames": frame_idx,
        "raw_detections": quality["total_raw_detections"],
        "filtered_detections": quality["total_filtered_detections"],
        "avg_filtered_detections_per_frame": round(quality["total_filtered_detections"] / frame_idx, 2),
        "same_class_suppressed": quality["total_same_class_suppressed"],
        "cross_class_suppressed": quality["total_cross_class_suppressed"],
        "total_suppressed": quality["total_same_class_suppressed"] + quality["total_cross_class_suppressed"],
        "suppression_rate_pct": round(100.0 * (quality["total_same_class_suppressed"] + quality["total_cross_class_suppressed"]) / max(1, quality["total_raw_detections"]), 2),
        "unique_vehicles_counted": summary_after.total_unique_vehicles,
        "by_class_counts": summary_after.by_class,
        "raw_class_flickers": quality["raw_class_flickers"],
        "stabilized_class_flickers": quality["stabilized_class_flickers"],
        "flicker_reduction_pct": round(100.0 * (quality["raw_class_flickers"] - quality["stabilized_class_flickers"]) / max(1, quality["raw_class_flickers"]), 2),
        "active_tracks": quality["active_tracks"],
        "total_tracks_created": quality["total_tracks_created"]
    }
    
    out_data = {
        "before": before_results,
        "after": after_results
    }
    
    print("\n" + "="*50)
    print("REGRESSION COMPARISON RESULTS")
    print("="*50)
    print(json.dumps(out_data, indent=2))
    
    with open("benchmark_outputs/regression_comparison.json", "w") as f:
        json.dump(out_data, f, indent=2)

if __name__ == "__main__":
    run_precision_regression_benchmark()
