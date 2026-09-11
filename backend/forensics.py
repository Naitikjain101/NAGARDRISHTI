import sys
import logging
import time
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from ultralytics import YOLO
from ai.common.device import get_device_info
from ai.pothole.config import DEFAULT_POTHOLE_MODEL

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forensics")

FORENSICS_DIR = Path("backend/results/pothole_forensics")
FORENSICS_DIR.mkdir(parents=True, exist_ok=True)

def run_raw_inference(video_path: Path):
    logger.info(f"--- RAW INFERENCE TEST: {video_path.name} ---")
    device = get_device_info().device_str
    model = YOLO(DEFAULT_POTHOLE_MODEL)
    model.to(device)

    from video.reader import iter_frames
    
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    resolutions = [320, 416, 512, 640]
    
    results_matrix = {sz: {th: 0 for th in thresholds} for sz in resolutions}
    total_frames = 0
    
    for frame_idx, timestamp, frame in iter_frames(video_path, interval=10, max_frames=20):
        total_frames += 1
        for sz in resolutions:
            for th in thresholds:
                # Raw predict
                res = model.predict(source=frame, imgsz=sz, conf=th, device=device, verbose=False, stream=False)
                if res and res[0].boxes:
                    results_matrix[sz][th] += len(res[0].boxes)
            
    logger.info("Raw Detections Count (over 20 sampled frames):")
    for sz in resolutions:
        for th in thresholds:
            logger.info(f"  imgsz={sz}, conf={th:.2f} -> {results_matrix[sz][th]} detections")
            
    return results_matrix

def run_pipeline_comparison(video_path: Path):
    logger.info(f"\n--- PIPELINE COMPARISON: {video_path.name} ---")
    from ai.unified.processor import UnifiedVideoProcessor
    
    processor = UnifiedVideoProcessor()
    
    result = processor.process(
        video_path=str(video_path),
        video_id=video_path.stem + "_forensic",
        results_dir="backend/results",
        progress_callback=None
    )
    
    stats = {
        "raw": 0,
        "suppressed": 0,
        "confirmed": 0,
        "frames_with_detections": 0
    }
    
    for frame in result.frames:
        if frame.pothole_detections:
            stats["raw"] += len(frame.pothole_detections)
            stats["frames_with_detections"] += 1
            
    summary_events = result.pothole_events
    confirmed = sum(1 for e in summary_events if e.status.value == "confirmed")
    suppressed = sum(1 for e in summary_events if e.status.value == "suppressed")
    stats["confirmed"] = confirmed
    stats["suppressed"] = suppressed
    
    logger.info(f"Total Frames Processed: {len(result.frames)}")
    logger.info(f"Raw Detections (across all frames): {stats['raw']}")
    logger.info(f"Confirmed Events: {stats['confirmed']}")
    logger.info(f"Suppressed Events: {stats['suppressed']}")
    
    return result, stats

if __name__ == "__main__":
    v_road = Path("video/test_data/road_test.mp4")
    v_traffic = Path("video/test_data/traffic_test.mp4")
    
    if v_road.exists():
        run_raw_inference(v_road)
        run_pipeline_comparison(v_road)
        
    if v_traffic.exists():
        run_raw_inference(v_traffic)
        run_pipeline_comparison(v_traffic)
