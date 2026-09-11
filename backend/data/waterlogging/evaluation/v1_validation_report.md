# Waterlogging V1 — Forensic Validation Report

## MODEL
Path: `runs/segment/models/waterlogging/v1/weights/best.pt`

## DATASET
95 total images. 
Single-source frame split — generalization not established.

## TRAINING INFORMATION
- mAP50 (Box): 0.9790
- mAP50-95 (Box): 0.8318
- mAP50 (Mask): 0.9784
- mAP50-95 (Mask): 0.7833
- Box Loss: 0.6118
- Seg Loss: 0.8491

## PERFORMANCE
- Total Processing Time: 105.23s
- Overall FPS: 25.98
- Inference FPS: 39.60
- Total Frames: 2734

## DETECTION STATISTICS
- Raw Detections: 4500
- Validated Events: 22878
- Avg Confidence: 0.86 (Min: 0.40, Max: 1.00)
- Avg Area Ratio: 0.604 (Max: 0.952)

## GT COMPARISON (On 95 annotated frames)
- True Positives: 0
- False Positives: 93
- False Negatives: 2
- Precision: 0.00
- Recall: 0.00

## TEMPORAL STABILITY
- Stable Events (>30 frames): 17
- Intermittent (6-30 frames): 0
- Fragmented/One-off (<=5 frames): 0

## WATERLOGGING V1 VERDICT

Model: V1 Segmentation
Dataset: 95 images
Source Video: 17929886-uhd_3840_2160_59fps_compressed.mp4

Precision: 0.00
Recall: 0.00
mAP50: 0.9784
mAP50-95: 0.7833

Inference FPS: 39.60
Average latency: 25.25 ms

Raw detections: 4500
Validated events: 22878

False positives: 93
False negatives: 2

Temporal stability: 17 stable, 0 intermittent, 0 fragmented

Dataset limitations: Single-source video limits environmental variance.

GENERALIZATION:
[NOT ESTABLISHED] (Single source video)

PRODUCTION STATUS:
[NOT READY]

Recommendation for V2: 
Collect frames from different environments, lighting conditions, and camera angles. Hard-negative mining on dry reflective roads is required.
