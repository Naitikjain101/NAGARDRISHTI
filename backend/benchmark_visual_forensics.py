import sys
import os
import time
import json
import csv
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np
import torch
from ultralytics import YOLO

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))
from ai.common.device import get_device_info

VIDEO_PATH = "/Users/naitikjain/Downloads/Nagar drishti/traffic_test-2-2-2.mp4"
BASE_OUT_DIR = Path(__file__).parent.parent / "benchmark_outputs"
MODELS = {
    "yolov8n": "yolov8n.pt",
    "yolo11n": "yolo11n.pt",
    "yolo26n": "yolo26n.pt"
}

CONF_THRESHOLD = 0.30
IMGSZ = 640
MAX_FRAMES = 300

# COCO classes for vehicles (and person for context)
COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

VEHICLE_CLASS_IDS = [1, 2, 3, 5, 7]

CLASS_COLORS = {
    "car": (255, 100, 0),        # Blue-ish
    "motorcycle": (0, 200, 255),  # Yellow
    "bicycle": (0, 255, 0),       # Green
    "bus": (255, 0, 255),        # Magenta
    "truck": (0, 100, 255),       # Orange
    "person": (200, 200, 200)     # Gray
}

def compute_box_geometry(b1, b2):
    """
    Compute IoU, IoMin (intersection over min area),
    and center containment between b1 and b2 [x1, y1, x2, y2].
    """
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    
    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h
    
    area1 = max(0, (b1[2] - b1[0]) * (b1[3] - b1[1]))
    area2 = max(0, (b2[2] - b2[0]) * (b2[3] - b2[1]))
    
    union_area = area1 + area2 - inter_area
    iou = inter_area / union_area if union_area > 0 else 0.0
    
    min_area = min(area1, area2)
    iomin = inter_area / min_area if min_area > 0 else 0.0
    
    # Center containment
    c1 = ((b1[0] + b1[2]) / 2.0, (b1[1] + b1[3]) / 2.0)
    c2 = ((b2[0] + b2[2]) / 2.0, (b2[1] + b2[3]) / 2.0)
    
    c1_in_b2 = (b2[0] <= c1[0] <= b2[2]) and (b2[1] <= c1[1] <= b2[3])
    c2_in_b1 = (b1[0] <= c2[0] <= b1[2]) and (b1[1] <= c2[1] <= b1[3])
    center_contained = c1_in_b2 or c2_in_b1
    
    return {
        "iou": iou,
        "iomin": iomin,
        "area1": area1,
        "area2": area2,
        "center_contained": center_contained,
        "c1_in_b2": c1_in_b2,
        "c2_in_b1": c2_in_b1
    }

def categorize_pair(det1, det2, geom):
    """
    Categorize overlap between det1 and det2:
    - same-class duplicate
    - cross-class duplicate
    - legitimate overlapping objects
    - uncertain
    """
    c1, c2 = det1["class_name"], det2["class_name"]
    iou = geom["iou"]
    iomin = geom["iomin"]
    center_contained = geom["center_contained"]
    
    if "person" in [c1, c2] and ("motorcycle" in [c1, c2] or "bicycle" in [c1, c2]):
        return "legitimate overlapping objects", "Rider + Vehicle interaction"
    
    if c1 == c2:
        if iou >= 0.70 or iomin >= 0.85:
            return "same-class duplicate", f"Same class ({c1}) with high IoU ({iou:.2f})"
        elif iou >= 0.30:
            return "uncertain", f"Same class ({c1}) with moderate IoU ({iou:.2f})"
        else:
            return "legitimate overlapping objects", f"Same class ({c1}) nearby"
            
    # Cross-class vehicle comparisons (e.g. car vs truck, motorcycle vs bicycle, car vs bus)
    vehicle_confusable = [
        {"car", "truck"}, {"motorcycle", "bicycle"}, {"bus", "truck"}, {"car", "bus"}, {"motorcycle", "car"}
    ]
    is_confusable = {c1, c2} in vehicle_confusable
    
    if is_confusable:
        if iou >= 0.65 or (iomin >= 0.80 and center_contained):
            return "cross-class duplicate", f"Cross-class ({c1} vs {c2}) high overlap/containment (IoU={iou:.2f}, IoMin={iomin:.2f})"
        elif iou >= 0.35:
            return "uncertain", f"Cross-class ({c1} vs {c2}) partial overlap (IoU={iou:.2f})"
        else:
            return "legitimate overlapping objects", f"Cross-class ({c1} vs {c2}) adjacent vehicles"
            
    if iou >= 0.70 or (iomin >= 0.85 and center_contained):
        return "cross-class duplicate", f"Cross-class ({c1} vs {c2}) high containment"
    elif iou >= 0.30:
        return "uncertain", f"Cross-class ({c1} vs {c2}) moderate overlap"
    else:
        return "legitimate overlapping objects", f"Distinct classes ({c1} vs {c2})"

def run_visual_forensics():
    device_info = get_device_info()
    device = device_info.device_str
    print(f"=== Urban Watch Visual Forensic Benchmark ===")
    print(f"Device: {device} ({device_info.device_name})")
    print(f"Video: {VIDEO_PATH}")
    print(f"Confidence: {CONF_THRESHOLD} | Imgsz: {IMGSZ} | Max Frames: {MAX_FRAMES}")
    
    BASE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    all_suspicious = []
    model_summaries = {}
    rule_evaluations = {m_key: {"rule_A": {"suppressed": 0, "true_dup_suppressed": 0, "false_suppressed": 0},
                                "rule_B": {"suppressed": 0, "true_dup_suppressed": 0, "false_suppressed": 0},
                                "rule_C": {"suppressed": 0, "true_dup_suppressed": 0, "false_suppressed": 0},
                                "rule_smart": {"suppressed": 0, "true_dup_suppressed": 0, "false_suppressed": 0}}
                        for m_key in MODELS}
    
    for model_key, model_file in MODELS.items():
        print(f"\n" + "="*40)
        print(f"Evaluating Model: {model_key} ({model_file})")
        print(f"="*40)
        
        m_dir = BASE_OUT_DIR / model_key
        frames_dir = m_dir / "frames"
        m_dir.mkdir(parents=True, exist_ok=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        model = YOLO(model_file)
        
        cap = cv2.VideoCapture(VIDEO_PATH)
        if not cap.isOpened():
            print(f"ERROR: Cannot open {VIDEO_PATH}")
            return
            
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        video_out_path = m_dir / "annotated_300frames.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(video_out_path), fourcc, fps_in, (width, height))
        
        frame_idx = 0
        total_detections = 0
        class_hist = defaultdict(int)
        dup_category_hist = defaultdict(int)
        suspicious_frames = set()
        
        small_dets = 0
        occluded_dets = 0
        
        # Track detections across frames for temporal review
        frame_data_list = []
        
        while frame_idx < MAX_FRAMES:
            ret, frame = cap.read()
            if not ret:
                break
                
            orig_frame = frame.copy()
            
            # Predict
            results = model.predict(
                source=frame,
                imgsz=IMGSZ,
                conf=CONF_THRESHOLD,
                classes=list(COCO_CLASSES.keys()),
                device=device,
                verbose=False
            )[0]
            
            boxes = results.boxes.xyxy.cpu().numpy() if results.boxes else []
            clses = results.boxes.cls.cpu().numpy() if results.boxes else []
            confs = results.boxes.conf.cpu().numpy() if results.boxes else []
            
            detections = []
            for i in range(len(boxes)):
                c_id = int(clses[i])
                c_name = COCO_CLASSES.get(c_id, f"class_{c_id}")
                box = [float(x) for x in boxes[i]]
                cf = float(confs[i])
                
                # We focus primarily on vehicle classes
                area = (box[2] - box[0]) * (box[3] - box[1])
                is_small = area < 1200
                if is_small and c_name in VEHICLE_CLASSES:
                    small_dets += 1
                    
                total_detections += 1
                class_hist[c_name] += 1
                
                detections.append({
                    "id": i,
                    "class_id": c_id,
                    "class_name": c_name,
                    "conf": cf,
                    "box": box,
                    "area": area,
                    "is_small": is_small
                })
                
            # Pairwise overlap analysis
            frame_suspicious = []
            num_det = len(detections)
            pair_geoms = {}
            
            for i in range(num_det):
                for j in range(i + 1, num_det):
                    d1, d2 = detections[i], detections[j]
                    geom = compute_box_geometry(d1["box"], d2["box"])
                    pair_geoms[(i, j)] = geom
                    
                    if geom["iou"] > 0.15 or geom["iomin"] > 0.40:
                        category, reason = categorize_pair(d1, d2, geom)
                        dup_category_hist[category] += 1
                        
                        item = {
                            "model": model_key,
                            "frame": frame_idx,
                            "det1": {"class": d1["class_name"], "conf": round(d1["conf"], 3), "box": [round(x, 1) for x in d1["box"]]},
                            "det2": {"class": d2["class_name"], "conf": round(d2["conf"], 3), "box": [round(x, 1) for x in d2["box"]]},
                            "iou": round(geom["iou"], 3),
                            "iomin": round(geom["iomin"], 3),
                            "center_contained": geom["center_contained"],
                            "category": category,
                            "reason": reason
                        }
                        
                        if category in ["same-class duplicate", "cross-class duplicate", "uncertain"]:
                            frame_suspicious.append(item)
                            all_suspicious.append(item)
                            suspicious_frames.add(frame_idx)
                            
            # Simulate Duplicate Suppression Rules
            # Rule A: IoU >= 0.70
            # Rule B: IoU >= 0.80
            # Rule C: IoU >= 0.85
            # Rule Smart: same-class IoU >= 0.75 OR (cross-class confusable IoU >= 0.65 or (IoMin >= 0.80 and center_contained))
            
            def evaluate_rule(rule_fn):
                suppressed_indices = set()
                # greedy suppression by confidence
                sorted_indices = sorted(range(num_det), key=lambda idx: detections[idx]["conf"], reverse=True)
                for si in range(len(sorted_indices)):
                    idx_high = sorted_indices[si]
                    if idx_high in suppressed_indices:
                        continue
                    for sj in range(si + 1, len(sorted_indices)):
                        idx_low = sorted_indices[sj]
                        if idx_low in suppressed_indices:
                            continue
                        pair_key = (min(idx_high, idx_low), max(idx_high, idx_low))
                        geom = pair_geoms.get(pair_key)
                        if not geom:
                            continue
                        should_suppress, is_real_dup = rule_fn(detections[idx_high], detections[idx_low], geom)
                        if should_suppress:
                            suppressed_indices.add(idx_low)
                            return should_suppress, is_real_dup
                return False, False
                
            for i in range(num_det):
                for j in range(i + 1, num_det):
                    geom = pair_geoms[(i, j)]
                    d1, d2 = detections[i], detections[j]
                    cat, _ = categorize_pair(d1, d2, geom)
                    is_true_dup = cat in ["same-class duplicate", "cross-class duplicate"]
                    is_legit = cat == "legitimate overlapping objects"
                    
                    # Rule A
                    if geom["iou"] >= 0.70:
                        rule_evaluations[model_key]["rule_A"]["suppressed"] += 1
                        if is_true_dup:
                            rule_evaluations[model_key]["rule_A"]["true_dup_suppressed"] += 1
                        elif is_legit:
                            rule_evaluations[model_key]["rule_A"]["false_suppressed"] += 1
                            
                    # Rule B
                    if geom["iou"] >= 0.80:
                        rule_evaluations[model_key]["rule_B"]["suppressed"] += 1
                        if is_true_dup:
                            rule_evaluations[model_key]["rule_B"]["true_dup_suppressed"] += 1
                        elif is_legit:
                            rule_evaluations[model_key]["rule_B"]["false_suppressed"] += 1
                            
                    # Rule C
                    if geom["iou"] >= 0.85:
                        rule_evaluations[model_key]["rule_C"]["suppressed"] += 1
                        if is_true_dup:
                            rule_evaluations[model_key]["rule_C"]["true_dup_suppressed"] += 1
                        elif is_legit:
                            rule_evaluations[model_key]["rule_C"]["false_suppressed"] += 1
                            
                    # Smart Geometric Rule
                    smart_suppress = False
                    if d1["class_name"] == d2["class_name"] and geom["iou"] >= 0.75:
                        smart_suppress = True
                    elif d1["class_name"] != d2["class_name"]:
                        c_set = {d1["class_name"], d2["class_name"]}
                        if c_set in [{"car", "truck"}, {"motorcycle", "bicycle"}, {"bus", "truck"}, {"car", "bus"}]:
                            if geom["iou"] >= 0.65 or (geom["iomin"] >= 0.80 and geom["center_contained"]):
                                smart_suppress = True
                                
                    if smart_suppress:
                        rule_evaluations[model_key]["rule_smart"]["suppressed"] += 1
                        if is_true_dup:
                            rule_evaluations[model_key]["rule_smart"]["true_dup_suppressed"] += 1
                        elif is_legit:
                            rule_evaluations[model_key]["rule_smart"]["false_suppressed"] += 1
            
            # Annotate Frame
            annotated_frame = frame.copy()
            # Draw header banner
            cv2.rectangle(annotated_frame, (0, 0), (width, 40), (20, 20, 20), -1)
            header_text = f"Urban Watch Forensic | {model_key.upper()} | Frame: {frame_idx:03d} | Dets: {len(detections)} | Suspicious: {len(frame_suspicious)}"
            cv2.putText(annotated_frame, header_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            
            for det in detections:
                b = [int(v) for v in det["box"]]
                c_name = det["class_name"]
                conf = det["conf"]
                color = CLASS_COLORS.get(c_name, (0, 255, 255))
                
                # Draw box
                cv2.rectangle(annotated_frame, (b[0], b[1]), (b[2], b[3]), color, 2)
                
                # Label
                label = f"{c_name} {conf:.2f}"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated_frame, (b[0], max(0, b[1] - 20)), (b[0] + lw + 6, max(20, b[1])), color, -1)
                cv2.putText(annotated_frame, label, (b[0] + 3, max(15, b[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                
            # If suspicious duplicates exist in this frame, highlight them
            for s in frame_suspicious:
                b1 = [int(v) for v in s["det1"]["box"]]
                b2 = [int(v) for v in s["det2"]["box"]]
                # Draw warning indicator
                mid_x = (b1[0] + b2[0]) // 2
                mid_y = (b1[1] + b2[1]) // 2
                tag = "DUP-SAME" if s["category"] == "same-class duplicate" else ("DUP-CROSS" if s["category"] == "cross-class duplicate" else "AMBIGUOUS")
                color_warn = (0, 0, 255) if "duplicate" in s["category"] else (0, 165, 255)
                cv2.putText(annotated_frame, f"! {tag} (IoU:{s['iou']})", (mid_x, max(30, mid_y)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color_warn, 2)
            
            writer.write(annotated_frame)
            
            # Save key sampled frames (every 30 frames OR if frame contains suspicious duplicates)
            if frame_idx % 30 == 0 or (len(frame_suspicious) > 0 and frame_idx % 10 == 0):
                frame_save_path = frames_dir / f"frame_{frame_idx:03d}.jpg"
                cv2.imwrite(str(frame_save_path), annotated_frame)
                
            frame_idx += 1
            
        cap.release()
        writer.release()
        
        model_summaries[model_key] = {
            "total_frames": frame_idx,
            "total_detections": total_detections,
            "avg_detections_per_frame": round(total_detections / frame_idx, 2) if frame_idx else 0,
            "class_distribution": dict(class_hist),
            "duplicate_breakdown": dict(dup_category_hist),
            "suspicious_frame_count": len(suspicious_frames),
            "small_distant_vehicles": small_dets,
            "video_path": str(video_out_path),
            "sampled_frames_path": str(frames_dir)
        }
        print(f"Done evaluating {model_key}. Detections: {total_detections}, Suspicious pairs: {len([s for s in all_suspicious if s['model'] == model_key])}")
        
    # Write CSV Report of Suspicious Detections
    csv_path = BASE_OUT_DIR / "suspicious_detections.csv"
    with open(csv_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Model", "Frame", "Det1_Class", "Det1_Conf", "Det1_Box", "Det2_Class", "Det2_Conf", "Det2_Box", "IoU", "IoMin", "CenterContained", "Category", "Reason"])
        for s in all_suspicious:
            writer.writerow([
                s["model"],
                s["frame"],
                s["det1"]["class"],
                s["det1"]["conf"],
                str(s["det1"]["box"]),
                s["det2"]["class"],
                s["det2"]["conf"],
                str(s["det2"]["box"]),
                s["iou"],
                s["iomin"],
                s["center_contained"],
                s["category"],
                s["reason"]
            ])
            
    # Write JSON Report
    json_path = BASE_OUT_DIR / "suspicious_detections.json"
    with open(json_path, "w") as f:
        json.dump(all_suspicious, f, indent=2)
        
    summary_path = BASE_OUT_DIR / "forensic_summary.json"
    full_output = {
        "model_summaries": model_summaries,
        "rule_evaluations": rule_evaluations
    }
    with open(summary_path, "w") as f:
        json.dump(full_output, f, indent=2)
        
    print("\n" + "="*50)
    print("VISUAL FORENSIC BENCHMARK COMPLETE")
    print("="*50)
    print(f"Outputs written to: {BASE_OUT_DIR}")
    print(json.dumps(full_output, indent=2))

if __name__ == "__main__":
    run_visual_forensics()
