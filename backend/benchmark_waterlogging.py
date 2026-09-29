"""
Urban Watch — Waterlogging Benchmark
Evaluates the performance, latency, and false positives for the waterlogging detection pipeline.
"""

import argparse
import logging
import os
import time
from tabulate import tabulate

from ai.unified.processor import UnifiedVideoProcessor

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_benchmark(video_path: str):
    logger.info("Starting Waterlogging Benchmark on %s", video_path)
    
    if not os.path.exists(video_path):
        logger.error("Video not found: %s", video_path)
        return
        
    processor = UnifiedVideoProcessor()
    results_dir = "benchmark_results"
    
    t0 = time.perf_counter()
    summary = processor.process(
        video_path=video_path,
        video_id="benchmark_waterlogging",
        results_dir=results_dir
    )
    t1 = time.perf_counter()
    
    total_time = t1 - t0
    
    # Extract Waterlogging Metrics
    wl_events = summary.waterlogging_events
    raw_detections = sum(len(f.waterlogging_detections) for f in summary.frames)
    
    # Since we don't have ground truth labels in this test, we log events as "detected events".
    # For a dry road test video, any detected event is a false positive.
    
    table = [
        ["Total Processing Time", f"{total_time:.2f} s"],
        ["Video Duration", f"{summary.video.duration_seconds:.2f} s"],
        ["Processed Frames", len(summary.frames)],
        ["Overall Pipeline FPS", f"{len(summary.frames)/total_time:.2f}"],
        ["Raw Waterlogging Detections", raw_detections],
        ["Validated Waterlogging Events", len(wl_events)]
    ]
    
    if summary.video.duration_seconds > 0:
        fp_per_min = (len(wl_events) / summary.video.duration_seconds) * 60
        table.append(["Events per minute", f"{fp_per_min:.2f}"])
        
    print("\n" + "="*50)
    print("WATERLOGGING BENCHMARK RESULTS")
    print("="*50)
    print(tabulate(table, headers=["Metric", "Value"], tablefmt="pretty"))
    print("="*50)
    
    if wl_events:
        print("\nDetected Waterlogging Events:")
        event_data = []
        for e in wl_events:
            event_data.append([
                e.event_id, 
                e.estimated_severity.value, 
                f"{e.max_confidence:.2f}",
                f"{e.max_area_ratio*100:.1f}%",
                e.span_frames
            ])
        print(tabulate(event_data, headers=["ID", "Severity", "Confidence", "Max Area", "Span Frames"], tablefmt="grid"))
    else:
        print("\nNo waterlogging events detected (0 False Positives if dry video).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Waterlogging Detector")
    parser.add_argument("--video", type=str, required=True, help="Path to test video")
    args = parser.parse_args()
    
    run_benchmark(args.video)
