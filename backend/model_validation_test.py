import asyncio
import os
import sys

# Must add backend to path to import ai correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai.unified.processor import UnifiedVideoProcessor

def run_test(video_id: str, video_path: str):
    print(f"--- Running Test for {video_id} ---")
    print(f"Video: {video_path}")
    processor = UnifiedVideoProcessor()
    result = processor.process(video_path=video_path, video_id=video_id, results_dir="results")
    
    print(f"Status: {result.status}")
    print(f"Error: {result.error}")
    print(f"Pothole Events: {len(result.pothole_events)}")
    print(f"Waterlogging Events: {len(result.waterlogging_events)}")
    print("---------------------------------------\n")

if __name__ == "__main__":
    # Test A: Zero Pothole
    zero_pothole_vid = "/Users/naitikjain/Documents/Nagar drishti mp4/16373790_3840_2160_30fps_compressed.mp4"
    if os.path.exists(zero_pothole_vid):
        run_test("test_zero_potholes", zero_pothole_vid)
    else:
        print("Test A Video Not Found")
        
    # Test B: Potholes
    pothole_vid = "/Users/naitikjain/Documents/Nagar drishti mp4/potholes.mp4"
    if os.path.exists(pothole_vid):
        run_test("test_potholes", pothole_vid)
    else:
        print("Test B Video Not Found")
