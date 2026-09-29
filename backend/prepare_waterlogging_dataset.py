import cv2
import os
import json
import shutil
import numpy as np
import math

VIDEO_PATH = "/Users/naitikjain/Downloads/Waterlogging/17929886-uhd_3840_2160_59fps_compressed.mp4"
BASE_DIR = "/Users/naitikjain/Documents/Nagardristi2.0/backend/data/waterlogging"

DIRS = {
    "raw": os.path.join(BASE_DIR, "raw"),
    "extracted": os.path.join(BASE_DIR, "extracted"),
    "selected": os.path.join(BASE_DIR, "selected"),
    "hard_negatives": os.path.join(BASE_DIR, "hard_negatives"),
    "rejected": os.path.join(BASE_DIR, "rejected"),
    "annotations": os.path.join(BASE_DIR, "annotations"),
    "metadata": os.path.join(BASE_DIR, "metadata"),
}

def setup_workspace():
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)
    # Copy original video to raw
    dest_video = os.path.join(DIRS["raw"], os.path.basename(VIDEO_PATH))
    if not os.path.exists(dest_video):
        shutil.copy2(VIDEO_PATH, dest_video)
    return dest_video

def compute_mse(img1, img2):
    # Convert to grayscale for structural comparison
    g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    err = np.sum((g1.astype("float") - g2.astype("float")) ** 2)
    err /= float(g1.shape[0] * g1.shape[1])
    return err

def create_contact_sheet(image_paths, output_path, cols=4, thumbnail_size=(320, 180)):
    if not image_paths:
        return
        
    rows = math.ceil(len(image_paths) / cols)
    sheet_width = cols * thumbnail_size[0]
    sheet_height = rows * thumbnail_size[1]
    
    sheet = np.zeros((sheet_height, sheet_width, 3), dtype=np.uint8)
    
    for idx, path in enumerate(image_paths):
        img = cv2.imread(path)
        if img is None:
            continue
        resized = cv2.resize(img, thumbnail_size)
        
        row = idx // cols
        col = idx % cols
        
        y = row * thumbnail_size[1]
        x = col * thumbnail_size[0]
        
        sheet[y:y+thumbnail_size[1], x:x+thumbnail_size[0]] = resized
        
        # Add label
        label = os.path.basename(path)
        cv2.putText(sheet, label, (x + 10, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
    cv2.imwrite(output_path, sheet)

def process_video():
    raw_video = setup_workspace()
    
    cap = cv2.VideoCapture(raw_video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    
    # Config
    target_fps = 2.0  # Extract 2 frames per second
    frame_interval = int(fps / target_fps)
    mse_threshold = 200.0  # Threshold for duplicate removal
    
    extracted_count = 0
    rejected_count = 0
    selected_count = 0
    
    last_selected_frame = None
    manifest_rows = [["image_path", "source_video", "frame_number", "timestamp", "category", "annotation_status"]]
    
    selected_paths = []
    
    print(f"Processing {os.path.basename(raw_video)}...")
    print(f"Resolution: {width}x{height}, FPS: {fps:.2f}, Duration: {duration:.2f}s")
    
    for frame_idx in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        timestamp = frame_idx / fps
        base_name = f"frame_{frame_idx:06d}.jpg"
        
        # Save to extracted
        ext_path = os.path.join(DIRS["extracted"], base_name)
        cv2.imwrite(ext_path, frame)
        extracted_count += 1
        
        is_duplicate = False
        if last_selected_frame is not None:
            mse = compute_mse(last_selected_frame, frame)
            if mse < mse_threshold:
                is_duplicate = True
                
        if is_duplicate:
            rej_path = os.path.join(DIRS["rejected"], base_name)
            shutil.copy2(ext_path, rej_path)
            rejected_count += 1
        else:
            sel_path = os.path.join(DIRS["selected"], base_name)
            ann_path = os.path.join(DIRS["annotations"], base_name)
            
            shutil.copy2(ext_path, sel_path)
            shutil.copy2(ext_path, ann_path)
            
            last_selected_frame = frame
            selected_count += 1
            selected_paths.append(sel_path)
            
            # Write metadata
            meta_path = os.path.join(DIRS["metadata"], base_name.replace(".jpg", ".json"))
            meta = {
                "source_video": os.path.basename(raw_video),
                "source_group": "17929886_uhd_3840_2160_59fps",
                "frame_index": frame_idx,
                "timestamp_seconds": round(timestamp, 3),
                "width": width,
                "height": height,
                "category": "waterlogging_positive", # Default assignment for human review
                "annotation_status": "pending"
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
                
            manifest_rows.append([base_name, os.path.basename(raw_video), str(frame_idx), str(round(timestamp, 3)), "waterlogging_positive", "pending"])
    
    cap.release()
    
    # Write manifest
    import csv
    manifest_path = os.path.join(BASE_DIR, "annotations_manifest.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(manifest_rows)
        
    # Write Contact Sheet
    contact_sheet_path = os.path.join(BASE_DIR, "contact_sheet.jpg")
    create_contact_sheet(selected_paths, contact_sheet_path)
    
    # Write Dataset Report
    report_path = os.path.join(BASE_DIR, "waterlogging_dataset_report.md")
    report = f"""# Waterlogging Dataset Report

## VIDEO ANALYSIS
----------------
**Resolution**: {width}x{height}
**FPS**: {fps:.2f}
**Duration**: {duration:.2f} seconds
**Total frames**: {total_frames}

## FRAME PROCESSING
----------------
**Initial sampling rate**: 2 frames per second (Interval: {frame_interval} frames)
**Frames initially extracted**: {extracted_count}
**Near-duplicates removed**: {rejected_count}
**Selected positive frames**: {selected_count} (Requires manual sorting)
**Selected hard-negative frames**: 0 (Currently grouped in selected; awaits manual review)
**Rejected frames**: {rejected_count}

## DATASET LOCATION
----------------
**Positive frames**: `{DIRS["selected"]}`
**Hard negatives**: `{DIRS["hard_negatives"]}` (Move items here from selected)
**Annotations**: `{DIRS["annotations"]}`
**Metadata**: `{DIRS["metadata"]}`
**Contact sheet**: `{contact_sheet_path}`
**Dataset report**: `{report_path}`

## WATERLOGGING SECTIONS
---------------------
(Pending human review)

## HARD NEGATIVE SECTIONS
----------------------
(Pending human review)

## DATASET STATUS
--------------
**Ready for annotation**: YES
**Training-ready**: NO

> **IMPORTANT**:
> This dataset is NOT training-ready until the selected images have proper ground-truth annotations and hard-negatives are manually sorted. Do not claim this is enough data to train a robust production model. This is the FIRST data source.
"""
    with open(report_path, "w") as f:
        f.write(report)
        
    print("\nDataset processing complete.")
    print(f"Extracted: {extracted_count} | Selected: {selected_count} | Rejected: {rejected_count}")
    print(f"Report saved to {report_path}")
    print(f"Contact sheet saved to {contact_sheet_path}")

if __name__ == "__main__":
    process_video()
