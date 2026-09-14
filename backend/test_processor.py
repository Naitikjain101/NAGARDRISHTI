import sys
import os
import uuid
from ai.unified.processor import UnifiedVideoProcessor

def main(video_path, results_dir="/Users/naitikjain/Documents/Nagardristi2.0/backend/results/test"):
    if not os.path.exists(results_dir):
        os.makedirs(results_dir, exist_ok=True)
    processor = UnifiedVideoProcessor()
    job_id = f"test_{uuid.uuid4().hex[:8]}"
    print(f"Processing video {video_path}...")
    result_summary = processor.process(video_path, job_id, results_dir)
        
    print("\n--- POTHOLES ---")
    events = result_summary.pothole_events
    print(f"Total pothole events: {len(events)}")
    for ev in events:
        if getattr(ev, 'max_confidence', 0) >= 0.65 or ev.max_confidence >= 0.65:
            print(f"Timestamp: {ev.first_seen_timestamp}s - {ev.last_seen_timestamp}s | Conf: {ev.max_confidence} | BBox: {ev.representative_bbox} | Detections: {ev.total_detections}")

    print("\n--- WATERLOGGING ---")
    wl_events = result_summary.waterlogging_events
    print(f"Total waterlogging events: {len(wl_events)}")
    for ev in wl_events:
        print(f"Timestamp: {ev.first_seen_timestamp}s - {ev.last_seen_timestamp}s | Conf: {ev.max_confidence} | Detections: {ev.total_detections}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python backend/test_processor.py <video_path>")
