import sys
import time
import cv2
import torch
import numpy as np
from pathlib import Path
from collections import defaultdict
from ultralytics import YOLO

# Add backend to path so we can import device manager
sys.path.insert(0, str(Path(__file__).parent))
from ai.common.device import get_device_info

VIDEO_PATH = "/Users/naitikjain/Downloads/Nagar drishti/traffic_test-2-2-2.mp4"
MODELS = ["yolov8n.pt", "yolo11n.pt", "yolo26n.pt"]
CONFS = [0.20, 0.25, 0.30, 0.40, 0.50]
MAX_FRAMES = 300 # Limit to 300 frames to keep benchmark run time reasonable

# COCO vehicle classes
VEHICLE_CLASSES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

def box_iou(box1, box2):
    """Calculate IoU between two boxes [x1, y1, x2, y2]"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0

def run_benchmark():
    device_info = get_device_info()
    device = device_info.device_str
    
    print(f"Starting Benchmark on {device}")
    print(f"Video: {VIDEO_PATH}")
    
    results = {}
    
    for model_name in MODELS:
        print(f"\nLoading {model_name}...")
        try:
            model = YOLO(model_name)
        except Exception as e:
            print(f"Failed to load {model_name}: {e}")
            continue
            
        results[model_name] = {}
        
        for conf in CONFS:
            print(f"  Testing conf={conf}...")
            cap = cv2.VideoCapture(VIDEO_PATH)
            if not cap.isOpened():
                print("Could not open video.")
                return
                
            frame_count = 0
            total_latency = 0.0
            
            total_detections = 0
            class_counts = defaultdict(int)
            duplicates = 0
            cross_class_duplicates = 0
            small_vehicles = 0
            
            # Simple stability tracking
            prev_boxes = []
            stable_detections = 0
            
            while True:
                ret, frame = cap.read()
                if not ret or frame_count >= MAX_FRAMES:
                    break
                    
                start_t = time.time()
                # Run inference
                res = model(frame, imgsz=640, conf=conf, classes=list(VEHICLE_CLASSES.keys()), verbose=False, device=device)[0]
                latency = time.time() - start_t
                total_latency += latency
                
                boxes = res.boxes.xyxy.cpu().numpy()
                cls = res.boxes.cls.cpu().numpy()
                confs = res.boxes.conf.cpu().numpy()
                
                frame_boxes = []
                for i in range(len(boxes)):
                    box = boxes[i]
                    c = int(cls[i])
                    total_detections += 1
                    class_counts[VEHICLE_CLASSES[c]] += 1
                    
                    area = (box[2] - box[0]) * (box[3] - box[1])
                    if area < 1000:
                        small_vehicles += 1
                        
                    frame_boxes.append({"box": box, "cls": c})
                    
                # Check duplicates within frame
                for i in range(len(frame_boxes)):
                    for j in range(i + 1, len(frame_boxes)):
                        b1 = frame_boxes[i]["box"]
                        b2 = frame_boxes[j]["box"]
                        c1 = frame_boxes[i]["cls"]
                        c2 = frame_boxes[j]["cls"]
                        
                        iou = box_iou(b1, b2)
                        if iou > 0.7:
                            duplicates += 1
                            if c1 != c2:
                                cross_class_duplicates += 1
                                
                # Check stability
                if prev_boxes:
                    for cur_b in frame_boxes:
                        best_iou = 0
                        for prev_b in prev_boxes:
                            if cur_b["cls"] == prev_b["cls"]:
                                iou = box_iou(cur_b["box"], prev_b["box"])
                                if iou > best_iou:
                                    best_iou = iou
                        if best_iou > 0.5:
                            stable_detections += 1
                            
                prev_boxes = frame_boxes
                frame_count += 1
                
            cap.release()
            
            avg_latency = total_latency / frame_count if frame_count else 0
            fps = 1.0 / avg_latency if avg_latency > 0 else 0
            avg_det_per_frame = total_detections / frame_count if frame_count else 0
            stability_rate = stable_detections / total_detections if total_detections else 0
            
            results[model_name][conf] = {
                "frames": frame_count,
                "total_det": total_detections,
                "avg_det": avg_det_per_frame,
                "fps": fps,
                "latency_ms": avg_latency * 1000,
                "classes": dict(class_counts),
                "dups": duplicates,
                "cross_dups": cross_class_duplicates,
                "small": small_vehicles,
                "stability": stability_rate
            }
            
    print("\n\n" + "="*50)
    print("BENCHMARK RESULTS")
    print("="*50)
    
    for model_name, conf_data in results.items():
        print(f"\nMODEL: {model_name}")
        for conf, stats in conf_data.items():
            print(f"  Conf: {conf:.2f} | FPS: {stats['fps']:.1f} | Avg Det: {stats['avg_det']:.2f} | "
                  f"Total: {stats['total_det']} | Dups: {stats['dups']} (Cross: {stats['cross_dups']}) | "
                  f"Small: {stats['small']} | Stability: {stats['stability']:.2f}")
            print(f"    Classes: {stats['classes']}")

if __name__ == "__main__":
    run_benchmark()
