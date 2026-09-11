import cv2
import os
import json
from ultralytics import YOLO
from pathlib import Path

# Config
MODEL_PATH = "backend/ai/pothole/weights/pothole_yolov8_peterhdd.pt"
VIDEOS = [
    "backend/video/test_data/road_test.mp4",
    "backend/video/test_data/traffic_test.mp4"
]
OUTPUT_DIR = Path("benchmark_outputs/pothole_forensics/raw_crops")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load model
print(f"Loading model: {MODEL_PATH}")
model = YOLO(MODEL_PATH)

results_data = []

def process_video(video_path):
    print(f"Processing {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open {video_path}")
        return
        
    frame_idx = 0
    crop_idx = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run inference (low conf to catch all)
        # Using 0.10 to see low-conf false positives too
        results = model(frame, conf=0.10, iou=0.45, verbose=False)
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Expand box slightly for context
                h, w = frame.shape[:2]
                pad_x = int((x2 - x1) * 0.5)
                pad_y = int((y2 - y1) * 0.5)
                
                cx1 = max(0, x1 - pad_x)
                cy1 = max(0, y1 - pad_y)
                cx2 = min(w, x2 + pad_x)
                cy2 = min(h, y2 + pad_y)
                
                crop = frame[cy1:cy2, cx1:cx2]
                if crop.size == 0:
                    continue
                    
                vid_name = Path(video_path).stem
                filename = f"{vid_name}_f{frame_idx}_c{conf:.2f}_{crop_idx}.jpg"
                filepath = OUTPUT_DIR / filename
                cv2.imwrite(str(filepath), crop)
                
                results_data.append({
                    "video": vid_name,
                    "frame": frame_idx,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "file": str(filepath)
                })
                crop_idx += 1
                
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx} frames...")
            
    cap.release()

for vid in VIDEOS:
    process_video(vid)
    
with open("benchmark_outputs/pothole_forensics/raw_data.json", "w") as f:
    json.dump(results_data, f, indent=2)

print(f"Total detections collected: {len(results_data)}")
