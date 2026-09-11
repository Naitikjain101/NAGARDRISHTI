# PHASE 4 AI BASELINE REPORT

This report establishes the forensic baseline for the AI pothole detection pipeline (Phase 4A), directly addressing the root cause of the behavior observed in Phase 3.

## 1. Forensic Methodology
We bypassed the application's event engine and tracking layers to run raw YOLO inference on the frames, and then compared this to the unified pipeline output. The goal was to trace the exact lifecycle of a detection:
`RAW YOLO DETECTION -> TRACKING -> SUPPRESSION -> CONFIRMED POTHOLE EVENT`

## 2. Raw Inference Test
We sampled 20 continuous frames from both videos and ran the raw YOLO26n model at various resolutions (320, 416, 512, 640) and confidence thresholds (0.10 to 0.50).

### `road_test.mp4` (256x144, 25 FPS)
The model demonstrated extreme hyper-sensitivity across ALL resolutions and thresholds.
- **640px, conf=0.10**: 59 raw detections in 20 frames (~3 per frame)
- **640px, conf=0.25 (Production config)**: 43 raw detections in 20 frames (~2.15 per frame)
- **640px, conf=0.50**: 31 raw detections in 20 frames (~1.55 per frame)

### `traffic_test.mp4` (3840x2160, 60 FPS)
The model was surprisingly silent on 4K footage.
- **320px, 416px, 512px**: 0 raw detections at any confidence threshold.
- **640px, conf=0.25**: 3 raw detections in 20 frames.

## 3. Pipeline Comparison

### `road_test.mp4`
- **Total Frames**: 1005
- **Raw Detections**: 1773
- **Confirmed Events**: 58
- **Suppressed Events**: 2

**Analysis**: The 58 pothole events reported are a direct result of the model generating 1,773 raw bounding boxes on normal road texture, shadows, and compression artifacts. The tracker grouped these 1,773 noisy detections into 58 distinct spatio-temporal clusters. Because there are almost no vehicles in this video, the interaction suppressor had nothing to suppress against.

### `traffic_test.mp4`
- **Total Frames**: 902
- **Raw Detections**: 15
- **Confirmed Events**: 0
- **Suppressed Events**: 5
- **Vehicle Count**: 220 unique vehicles

**Analysis**: The model generated only 15 raw detections across the entire 15-second 4K clip. The tracker formed 5 event candidates from these 15 detections. Because this is high-density traffic, all 5 candidates spatially intersected with the 220 active vehicle tracks (likely triggering on vehicle bodies/shadows), and the suppression engine successfully killed all 5, resulting in 0 confirmed events.

## 4. False Positive Analysis & Root Cause

**ROOT CAUSE: BAD MODEL QUALITY (YOLO26n)**
The current `pothole_yolo26n_640.pt` model is fundamentally flawed. It is not generalizing to the concept of a "pothole". Instead, it appears to have heavily overfit to generic road textures or specific dataset artifacts. 
- In low-res/compressed footage (`road_test.mp4`), it hallucinates potholes everywhere (1,773 detections).
- In high-res/crisp footage (`traffic_test.mp4`), it fails to detect anything on the road itself, only occasionally hallucinating on vehicles (15 detections).

No amount of downstream filtering, tracking, or confidence thresholding can fix a model that fundamentally outputs 1.7 false positives per frame on an empty road.

## 5. Next Steps (Phase 4B)
As mandated by the instructions: *"If the current pothole model performs poorly in raw inference: DO NOT try to fix it using arbitrary filtering. Search for better legitimate pretrained pothole models."*

We will now abandon the YOLO26n weights and search HuggingFace / Ultralytics Hub / GitHub for a legitimate, high-quality, pre-trained pothole detection model to replace it. We will write `MODEL_COMPARISON_REPORT.md` once candidate models are evaluated.
