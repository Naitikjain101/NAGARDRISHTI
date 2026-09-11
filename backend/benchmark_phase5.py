import os
from pathlib import Path
from ai.unified.processor import UnifiedVideoProcessor
from ai.pothole.config import DEFAULT_POTHOLE_MODEL

def main():
    print("--- RUNNING PHASE 5 ROAD-AWARE BENCHMARK ---")
    processor = UnifiedVideoProcessor()
    
    v_road = Path("video/test_data/road_test.mp4")
    v_traffic = Path("video/test_data/traffic_test.mp4")
    
    for v_path in [v_road, v_traffic]:
        if not v_path.exists():
            print(f"Skipping {v_path} (not found)")
            continue
            
        print(f"\nProcessing {v_path.name}...")
        result = processor.process(
            video_path=str(v_path),
            video_id=v_path.stem + "_phase5",
            results_dir="backend/results",
            progress_callback=None
        )
        
        print(f"\n--- RESULTS FOR {v_path.name} ---")
        print(f"Total Frames: {result.video.frame_count}")
        print(f"FPS: {result.timing.get('total_frame', {}).get('fps', 0)}")
        
        # Read rejection stats
        import json
        phase5_dir = Path("backend/results/phase5")
        stats_file = phase5_dir / f"{v_path.stem}_phase5_rejection_statistics.json"
        if stats_file.exists():
            with open(stats_file, "r") as f:
                stats = json.load(f)
            print(f"Raw Detections: {stats['total_raw']}")
            print(f"Rejected ROI: {stats['rejected_roi']}")
            print(f"Rejected Geometry: {stats['rejected_geometry']}")
            print(f"Rejected Vehicle Overlap: {stats['rejected_vehicle_overlap']}")
            print(f"Rejected Temporal Noise: {stats['rejected_temporal_noise']}")
            
        print(f"Confirmed Events: {len(result.pothole_events)}")

if __name__ == "__main__":
    main()
