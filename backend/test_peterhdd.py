import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ultralytics import YOLO
from ai.common.device import get_device_info
from video.reader import iter_frames

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_peterhdd")

def test_model(video_path: Path, model_path: str):
    logger.info(f"--- RAW INFERENCE TEST: {video_path.name} ---")
    device = get_device_info().device_str
    model = YOLO(model_path)
    model.to(device)

    thresholds = [0.25, 0.40]
    resolutions = [640]
    
    results_matrix = {sz: {th: 0 for th in thresholds} for sz in resolutions}
    total_frames = 0
    
    for frame_idx, timestamp, frame in iter_frames(video_path, interval=10, max_frames=20):
        total_frames += 1
        for sz in resolutions:
            for th in thresholds:
                res = model.predict(source=frame, imgsz=sz, conf=th, device=device, verbose=False, stream=False)
                if res and res[0].boxes:
                    results_matrix[sz][th] += len(res[0].boxes)
            
    for sz in resolutions:
        for th in thresholds:
            logger.info(f"  imgsz={sz}, conf={th:.2f} -> {results_matrix[sz][th]} detections")

if __name__ == "__main__":
    v_road = Path("video/test_data/road_test.mp4")
    v_traffic = Path("video/test_data/traffic_test.mp4")
    model_p = "ai/pothole/weights/pothole_yolov8_peterhdd.pt"
    
    if v_road.exists():
        test_model(v_road, model_p)
    if v_traffic.exists():
        test_model(v_traffic, model_p)
