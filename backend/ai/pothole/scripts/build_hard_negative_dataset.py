import os
import cv2
import json
import random
import shutil
from pathlib import Path
from ultralytics import YOLO

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
DATASETS_DIR = BASE_DIR / "datasets" / "pothole_hard_negative"
VIDEOS_DIR = BASE_DIR / "backend" / "video" / "test_data"

ROAD_TEST = VIDEOS_DIR / "road_test.mp4"
TRAFFIC_TEST = VIDEOS_DIR / "traffic_test.mp4"

# Create directories
splits = ["train", "val", "test"]
for split in splits:
    (DATASETS_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
    (DATASETS_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

# Generate data.yaml
yaml_content = f"""path: {DATASETS_DIR.absolute()}
train: images/train
val: images/val
test: images/test

names:
  0: pothole
"""
with open(DATASETS_DIR / "data.yaml", "w") as f:
    f.write(yaml_content)

print(f"Created dataset structure at {DATASETS_DIR}")

def get_split(frame_idx, total_frames):
    # Scene-based splitting:
    # 0-70% Train, 70-90% Val, 90-100% Test
    ratio = frame_idx / total_frames
    if ratio < 0.70:
        return "train"
    elif ratio < 0.90:
        return "val"
    else:
        return "test"

# To get labels for genuine potholes, we will use the baseline model to auto-annotate road_test, 
# keeping high confidence ones, filtering them carefully.
MODEL_PATH = BASE_DIR / "backend/ai/pothole/weights/pothole_yolov8_peterhdd.pt"
print(f"Loading baseline model for pseudo-labeling: {MODEL_PATH}")
model = YOLO(MODEL_PATH)

def process_video(video_path, is_genuine=False):
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_name = video_path.stem
    
    frame_idx = 0
    saved_count = 0
    
    # Process 1 frame every 5 frames to avoid near-duplicates
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_idx % 5 == 0:
            split = get_split(frame_idx, total_frames)
            img_name = f"{video_name}_f{frame_idx}.jpg"
            img_path = DATASETS_DIR / "images" / split / img_name
            lbl_path = DATASETS_DIR / "labels" / split / img_name.replace(".jpg", ".txt")
            
            # Save the image
            cv2.imwrite(str(img_path), frame)
            
            # Create label
            if is_genuine:
                # Get pseudo labels
                results = model(frame, conf=0.60, verbose=False)
                lines = []
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        # YOLO format: cls x_center y_center width height (normalized)
                        x1, y1, x2, y2 = box.xyxyn[0]
                        xc = (float(x1) + float(x2)) / 2
                        yc = (float(y1) + float(y2)) / 2
                        w = float(x2) - float(x1)
                        h = float(y2) - float(y1)
                        lines.append(f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
                        
                with open(lbl_path, "w") as f:
                    f.writelines(lines)
            else:
                # Hard negative: Empty label file
                open(lbl_path, "w").close()
                
            saved_count += 1
            
        frame_idx += 1
        
    cap.release()
    return saved_count

print("Extracting hard negatives from traffic_test.mp4...")
hn_count = process_video(TRAFFIC_TEST, is_genuine=False)

print("Extracting genuine potholes from road_test.mp4...")
gen_count = process_video(ROAD_TEST, is_genuine=True)

print(f"Dataset generated! Hard Negatives: {hn_count}, Genuine: {gen_count}, Total: {hn_count + gen_count}")
