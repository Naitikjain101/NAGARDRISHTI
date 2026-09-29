import os
import cv2
import time
import json
import csv
from pathlib import Path
from collections import defaultdict
from ultralytics import YOLO

# Config
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
WEIGHTS_DIR = BASE_DIR / "backend" / "ai" / "pothole" / "weights"
VIDEOS_DIR = BASE_DIR / "backend" / "video" / "test_data"
OUT_DIR = BASE_DIR / "benchmark_outputs" / "pothole_finetuning"

BASELINE_MODEL = WEIGHTS_DIR / "pothole_yolov8_peterhdd.pt"
FINETUNED_MODEL = WEIGHTS_DIR / "pothole_yolov8m_hardnegative_v1.pt"

ROAD_TEST = VIDEOS_DIR / "road_test.mp4"
TRAFFIC_TEST = VIDEOS_DIR / "traffic_test.mp4"

CONF_THRESHOLDS = [0.20, 0.25, 0.30, 0.40, 0.50]
IMGSZ = 640

# Create output dirs
(OUT_DIR / "baseline").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "finetuned").mkdir(parents=True, exist_ok=True)

def evaluate_model(model_path, video_path):
    print(f"Loading {model_path}...")
    model = YOLO(model_path)
    
    cap = cv2.VideoCapture(str(video_path))
    frame_count = 0
    start_time = time.time()
    
    # Store detections per confidence threshold
    results_by_conf = {c: 0 for c in CONF_THRESHOLDS}
    max_conf = 0.0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run inference at lowest threshold to collect all, then bucket
        # Actually just run at 0.10 and filter
        results = model(frame, conf=0.10, imgsz=IMGSZ, verbose=False)
        
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf > max_conf:
                    max_conf = conf
                
                for thresh in CONF_THRESHOLDS:
                    if conf >= thresh:
                        results_by_conf[thresh] += 1
                        
        frame_count += 1
        
        # Limit to 300 frames to save time in evaluation
        if frame_count >= 300:
            break
            
    end_time = time.time()
    cap.release()
    
    fps = frame_count / (end_time - start_time)
    latency = (end_time - start_time) / frame_count * 1000  # ms
    
    return {
        "fps": round(fps, 1),
        "latency_ms": round(latency, 2),
        "max_conf": round(max_conf, 3),
        "detections_by_conf": results_by_conf,
        "frames_processed": frame_count
    }

print("Running Evaluation Suite...")

eval_results = {}

# Evaluate Baseline
print("\n--- BASELINE EVALUATION ---")
if BASELINE_MODEL.exists():
    eval_results["baseline"] = {
        "hard_negatives": evaluate_model(BASELINE_MODEL, TRAFFIC_TEST),
        "genuine_potholes": evaluate_model(BASELINE_MODEL, ROAD_TEST)
    }
else:
    print(f"Error: Baseline model {BASELINE_MODEL} not found.")

# Evaluate Finetuned
print("\n--- FINETUNED EVALUATION ---")
if FINETUNED_MODEL.exists():
    eval_results["finetuned"] = {
        "hard_negatives": evaluate_model(FINETUNED_MODEL, TRAFFIC_TEST),
        "genuine_potholes": evaluate_model(FINETUNED_MODEL, ROAD_TEST)
    }
else:
    print(f"Warning: Finetuned model {FINETUNED_MODEL} not found. Did training complete?")
    
# Save JSON
with open(OUT_DIR / "comparison.json", "w") as f:
    json.dump(eval_results, f, indent=2)

# Save CSV (Summary at Conf 0.25)
csv_file = OUT_DIR / "comparison.csv"
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Model", "Test_Set", "FPS", "Latency(ms)", "Max_Conf", "Detections_Conf_0.25"])
    
    for model_name, data in eval_results.items():
        for test_set, metrics in data.items():
            writer.writerow([
                model_name,
                test_set,
                metrics["fps"],
                metrics["latency_ms"],
                metrics["max_conf"],
                metrics["detections_by_conf"][0.25]
            ])

print(f"Evaluation complete. Results saved to {OUT_DIR}")
