"""
Urban Watch — Phase 3 Benchmark Script
"""

import sys
import logging
import time
import json
from pathlib import Path

# Fix python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.unified.processor import UnifiedVideoProcessor

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("benchmark")

def run_benchmark(video_file: str, video_id: str):
    logger.info(f"--- BENCHMARKING {video_file} ---")
    video_path = Path("video/test_data") / video_file
    if not video_path.exists():
        logger.error(f"Missing {video_path}")
        return
        
    processor = UnifiedVideoProcessor()
    
    t0 = time.time()
    result = processor.process(
        video_path=str(video_path),
        video_id=video_id,
        results_dir="backend/results",
        progress_callback=lambda d, t: logger.info(f"  Progress: {d}/{t} frames") if d % 50 == 0 else None
    )
    t1 = time.time()
    
    logger.info("\n--- RESULTS ---")
    logger.info(f"Video: {video_file}")
    logger.info(f"Total processing time: {t1 - t0:.2f}s")
    
    if result.status == "failed":
        logger.error(f"Processing failed: {result.error}")
        return

    logger.info(f"Frames processed: {len(result.frames)}")
    logger.info(f"Average FPS: {result.timing['total_frame']['fps']:.1f}")
    
    if result.vehicle_counts:
        logger.info(f"Total Unique Vehicles: {result.vehicle_counts.total_unique_vehicles}")
        
    logger.info("\n--- POTHOLE EVENTS ---")
    logger.info(f"Total Pothole Events: {len(result.pothole_events)}")
    for ev in result.pothole_events:
        logger.info(f"  Event #{ev.event_id}: status={ev.status.value}, severity={ev.severity_score.value}, frames={ev.span_frames}, suppressed_by={ev.overlapping_vehicle_track_id}")

if __name__ == "__main__":
    run_benchmark("road_test.mp4", "bench_road")
    print("\n\n")
    run_benchmark("traffic_test.mp4", "bench_traffic")
