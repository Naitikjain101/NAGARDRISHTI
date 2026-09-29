import os
import csv
import json
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Data Paths (will be properly resolved or passed, but hardcoded to the workspace for now)
DATA_DIR = Path("data/waterlogging")
MANIFEST_PATH = DATA_DIR / "annotations_manifest.csv"
METADATA_DIR = DATA_DIR / "metadata"
SELECTED_DIR = DATA_DIR / "selected"
HARD_NEGATIVES_DIR = DATA_DIR / "hard_negatives"

class PolygonAnnotation(BaseModel):
    class_id: int
    class_name: str
    polygon: List[List[float]]



@router.get("/frames")
def get_frames():
    """Returns the list of frames from the manifest."""
    if not MANIFEST_PATH.exists():
        return {"frames": []}
        
    frames = []
    with open(MANIFEST_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frames.append(row)
    return {"frames": frames}

@router.get("/{frame_id}")
def get_annotation(frame_id: str):
    """Loads a single frame's metadata and annotations."""
    # frame_id expects the image basename, e.g., frame_000123.jpg
    meta_name = frame_id.replace(".jpg", ".json").replace(".png", ".json")
    meta_path = METADATA_DIR / meta_name
    
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Annotation data not found")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.post("/export")
def export_dataset():
    """Generates YOLO segmentation dataset from JSON metadata."""
    YOLO_DIR = DATA_DIR / "yolo_dataset"
    IMAGES_DIR = YOLO_DIR / "images" / "annotation_pool"
    LABELS_DIR = YOLO_DIR / "labels" / "annotation_pool"
    
    # Create structure
    for d in [IMAGES_DIR, LABELS_DIR]:
        os.makedirs(d, exist_ok=True)
        
    # Write data.yaml
    yaml_content = f"""path: {YOLO_DIR.absolute()}
train: images/annotation_pool
val: images/annotation_pool

names:
  0: waterlogging
"""
    with open(YOLO_DIR / "data.yaml", "w") as f:
        f.write(yaml_content)
        
    # Process metadata
    exported_count = 0
    for meta_file in METADATA_DIR.glob("*.json"):
        with open(meta_file, "r") as f:
            meta = json.load(f)
            
        status = meta.get("annotation_status", "pending")
        if status != "ANNOTATED":
            continue
            
        image_name = meta_file.name.replace(".json", ".jpg")
        src_img = SELECTED_DIR / image_name
        
        if not src_img.exists():
            continue
            
        # Copy image
        dst_img = IMAGES_DIR / image_name
        shutil.copy2(src_img, dst_img)
        
        # Write label
        label_name = meta_file.name.replace(".json", ".txt")
        label_path = LABELS_DIR / label_name
        
        with open(label_path, "w") as f_lbl:
            for ann in meta.get("annotations", []):
                class_id = ann.get("class_id", 0)
                polygon = ann.get("polygon", [])
                
                if len(polygon) < 3:
                    continue
                    
                # YOLO format: class_id x1 y1 x2 y2 ...
                points = []
                for pt in polygon:
                    # Ensure clamped [0, 1]
                    x = max(0.0, min(1.0, float(pt[0])))
                    y = max(0.0, min(1.0, float(pt[1])))
                    points.extend([f"{x:.6f}", f"{y:.6f}"])
                    
                line = f"{class_id} " + " ".join(points) + "\n"
                f_lbl.write(line)
                
        exported_count += 1
        
    return {"success": True, "exported_count": exported_count, "path": str(YOLO_DIR)}

@router.post("/{frame_id}")
def save_annotation(frame_id: str, data: Dict[str, Any]):
    """Saves polygons to JSON and updates manifest status."""
    meta_name = frame_id.replace(".jpg", ".json").replace(".png", ".json")
    meta_path = METADATA_DIR / meta_name
    
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Original metadata not found")
        
    # Read existing
    with open(meta_path, "r", encoding="utf-8") as f:
        existing = json.load(f)
        
    # Update annotations & status
    new_status = data.get("status", "PENDING")
    
    existing["annotations"] = data.get("annotations", [])
    existing["annotation_status"] = new_status
    
    # Save back
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
        
    # Update manifest
    if MANIFEST_PATH.exists():
        rows = []
        fields = []
        with open(MANIFEST_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            for row in reader:
                if row["image_path"] == frame_id:
                    row["annotation_status"] = new_status
                rows.append(row)
                
        with open(MANIFEST_PATH, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            
    # Handle hard negatives moving logic if necessary
    img_selected = SELECTED_DIR / frame_id
    img_hn = HARD_NEGATIVES_DIR / frame_id
    
    if new_status == "NO_WATERLOGGING":
        if img_selected.exists():
            shutil.move(str(img_selected), str(img_hn))
    elif new_status in ["ANNOTATED", "PENDING", "DIFFICULT", "SKIPPED"]:
        if img_hn.exists():
            shutil.move(str(img_hn), str(img_selected))
            
    return {"success": True, "status": new_status}


