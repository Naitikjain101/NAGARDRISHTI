import sys
from pathlib import Path
import cv2
import json

# Ensure backend is in python path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from ai.waterlogging.detector import WaterloggingDetector, ModelNotFoundError
from ai.waterlogging.config import DEFAULT_WATERLOGGING_MODEL

def main():
    print(f"Testing WaterloggingDetector using canonical model: {DEFAULT_WATERLOGGING_MODEL}")
    
    try:
        detector = WaterloggingDetector()
        detector.load()
    except ModelNotFoundError as e:
        print(f"FAIL: Model missing at {e.resolved_path}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: Error loading model: {e}")
        sys.exit(1)
        
    print("SUCCESS: Model loaded.")
    
    # Check classes
    names = detector._model.names
    print(f"Model classes: {names}")
    
    # Grab a frame
    video_path = Path(__file__).parent / "data" / "waterlogging" / "raw" / "17929886-uhd_3840_2160_59fps_compressed.mp4"
    if not video_path.exists():
        print(f"WARN: Test video not found at {video_path}, skipping inference test.")
        sys.exit(0)
        
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("FAIL: Could not read frame from video.")
        sys.exit(1)
        
    print(f"Successfully read frame: {frame.shape}")
    
    # Run inference
    try:
        dets, prof = detector.detect(frame, frame_index=0, timestamp=0.0)
        print(f"SUCCESS: Inference completed. Found {len(dets)} waterlogging detections.")
        print(f"Profiling: {prof}")
    except Exception as e:
        print(f"FAIL: Inference error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
