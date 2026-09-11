# Urban Watch — Project Architecture

**Phase 1: High-Precision AI Traffic Detection Foundation**

---

## Overview

Urban Watch is an AI-powered urban surveillance and traffic-analytics system built for the Smart India Hackathon (SIH).

Phase 1 establishes the reusable AI detection/tracking infrastructure. It does NOT implement the full SIH feature scope.

---

## Core Design Principles

1. **Accuracy over speed** — Detection quality is the primary metric. FPS is a secondary metric.
2. **No fake data** — Every metric in the system must be measured or explicitly labeled `NOT MEASURED`.
3. **No assumed classes** — Models must be inspected (`model.names`) before use. Filenames are not trusted.
4. **Separation of concerns** — Detection, tracking, traffic analytics, video I/O, and API are independent layers.
5. **Video playback independence** — HTML5 video plays immediately. AI processing never blocks playback.
6. **Device transparency** — The active compute device (MPS/CUDA/CPU) is always logged and exposed in API.
7. **Configuration over magic** — All thresholds live in `backend/ai/common/config.py`, not buried in logic.

---

## Repository Structure

```
urban-watch/
├── backend/
│   ├── main.py                    ← FastAPI entry point
│   ├── config.py                  ← Server-level configuration
│   ├── ai/
│   │   ├── common/
│   │   │   ├── device.py          ← Hardware detection (CUDA → MPS → CPU)
│   │   │   ├── timing.py          ← High-precision timing utilities
│   │   │   ├── schemas.py         ← Pydantic result schemas
│   │   │   └── config.py          ← AI thresholds and model configuration
│   │   ├── detection/
│   │   │   ├── classes.py         ← Required class definitions
│   │   │   ├── model_loader.py    ← Load, inspect, validate models
│   │   │   └── detector.py        ← Frame-level inference engine
│   │   ├── tracking/
│   │   │   └── tracker.py         ← ByteTrack multi-object tracker
│   │   ├── traffic/
│   │   │   ├── vehicle_counter.py ← Unique-ID vehicle counting
│   │   │   └── density.py         ← Rolling window traffic density
│   │   └── benchmarking/
│   │       ├── model_inspector.py ← Static model metadata inspector
│   │       └── benchmark_models.py← Full benchmark runner
│   ├── video/
│   │   ├── reader.py              ← Video metadata + frame extraction
│   │   ├── sampler.py             ← Frame interval sampling
│   │   ├── processor.py           ← End-to-end video processing pipeline
│   │   └── test_data/             ← Test videos (NOT committed to git)
│   ├── api/
│   │   ├── routes_video.py        ← /api/video/* endpoints
│   │   └── routes_ai.py           ← /api/ai/* endpoints
│   ├── tests/
│   │   ├── conftest.py            ← pytest fixtures
│   │   ├── test_device.py
│   │   ├── test_video_reader.py
│   │   ├── test_model_loader.py
│   │   ├── test_detector.py
│   │   ├── test_tracker.py
│   │   ├── test_vehicle_counter.py
│   │   ├── test_density.py
│   │   └── test_schemas.py
│   └── uploads/                   ← Uploaded videos (NOT committed)
│   └── results/                   ← AI result JSON files (NOT committed)
│
├── frontend/
│   ├── index.html                 ← Single-page testing UI
│   ├── css/
│   │   └── main.css
│   └── js/
│       ├── main.js                ← App init
│       ├── api.js                 ← Backend API client
│       ├── overlay.js             ← Canvas overlay (requestAnimationFrame)
│       └── dashboard.js           ← Status panel updates
│
├── README.md
├── PROJECT_ARCHITECTURE.md        ← This file
├── MODEL_POLICY.md
├── PHASE_1_REPORT.md
├── requirements.txt
└── .gitignore
```

---

## Data Flow

### Video Playback (Independent)

```
User uploads video
       ↓
POST /api/video/upload
       ↓
File stored at backend/uploads/{video_id}.mp4
       ↓
GET /api/video/{id}/stream
       ↓
HTML5 <video> plays immediately (browser handles decoding)
```

### AI Processing (Independent from Playback)

```
POST /api/ai/process/{video_id}
       ↓
background thread starts
       ↓
VideoReader → extracts metadata (width, height, fps, duration, codec)
       ↓
FrameSampler → yields frames at configured interval
       ↓
Detector → runs YOLO inference on MPS (or fallback device)
       ↓
Tracker → ByteTrack → assigns persistent track_id per object
       ↓
VehicleCounter → counts unique track_ids (vehicle classes only)
       ↓
DensityCalculator → 5-second rolling window of unique active vehicle IDs
       ↓
Timestamped JSON saved to backend/results/{video_id}.json
```

### Frontend Overlay

```
requestAnimationFrame loop
       ↓
read video.currentTime
       ↓
binary-search detection JSON for latest timestamp ≤ currentTime
       ↓
draw bboxes + labels on canvas
       ↓
never pause video / never wait for AI
```

---

## Component Contracts

### Detector Input/Output

**Input:** `np.ndarray` — original frame in BGR (OpenCV default), original resolution

**Output:**
```json
{
    "class_id": 2,
    "class_name": "car",
    "confidence": 0.87,
    "bbox": [x1, y1, x2, y2]
}
```
Bboxes are always in **original video pixel coordinates**.

---

### Tracker Input/Output

**Input:** List of `DetectionResult` for a single frame

**Output:**
```json
{
    "track_id": 17,
    "class_id": 2,
    "class_name": "car",
    "confidence": 0.87,
    "bbox": [x1, y1, x2, y2],
    "first_seen": 0.5,
    "last_seen": 3.2,
    "frames_seen": 84
}
```

Raw detections and tracked objects are **separate concepts**. A detection without a track ID is NOT discarded.

---

### Vehicle Counter

**Input:** Map of `{frame_index → List[TrackResult]}`

**Output:**
```json
{
    "total_unique_vehicles": 12,
    "by_class": {
        "car": 8,
        "motorcycle": 3,
        "bus": 1
    }
}
```

Vehicle count = count of unique `track_id` values across all frames.
It does NOT sum raw detection counts.

---

### Density Calculator

**Input:** Map of `{frame_index → List[TrackResult]}`, video FPS

**Output:**
```json
[
    {
        "window_start": 0.0,
        "window_end": 5.0,
        "unique_vehicle_count": 8,
        "density_level": "low"
    },
    {
        "window_start": 5.0,
        "window_end": 10.0,
        "unique_vehicle_count": 17,
        "density_level": "medium"
    }
]
```

Density levels are based on configurable thresholds in `config.py`.

---

## Device Selection

```python
# Priority: CUDA → MPS → CPU
if torch.cuda.is_available():
    device = "cuda"
elif torch.backends.mps.is_available():
    device = "mps"
else:
    device = "cpu"
```

Device is logged at startup and included in every AI result JSON.

Fallback is never silent. If device changes from expected, it is logged as a warning.

---

## Phase 1 Out of Scope

The following are intentionally deferred to later phases:

| Capability | Reason Deferred |
|---|---|
| Pothole detection | Requires specialized pretrained model — no valid COCO proxy |
| Helmet/no-helmet | Requires specialized pretrained model |
| Waterlogging | Requires specialized pretrained model |
| Road damage | Requires specialized pretrained model |
| ANPR/OCR | Requires separate pipeline (plate detection + OCR) |
| Accident detection | Requires specialized training data |
| GPS/GIS | Infrastructure not established yet |
| Department routing | Business logic — not AI foundation |
| Authentication | Security layer — not AI foundation |

---

## Configuration Locations

| Setting | Location |
|---|---|
| AI confidence thresholds | `backend/ai/common/config.py` |
| Traffic density thresholds | `backend/ai/common/config.py` |
| Frame sampling interval | `backend/ai/common/config.py` |
| Inference image size | `backend/ai/common/config.py` |
| Upload directory | `backend/config.py` |
| Results directory | `backend/config.py` |
| CORS origins | `backend/config.py` |

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| Backend framework | FastAPI | 0.128.8 |
| ASGI server | uvicorn | 0.39.0 |
| Deep learning | PyTorch | 2.8.0 |
| Object detection/tracking | Ultralytics | 8.4.41 |
| Computer vision | OpenCV | 4.13.0 |
| Numerical compute | NumPy | 2.0.2 |
| Data validation | Pydantic (FastAPI built-in) | — |
| System monitoring | psutil | 7.2.2 |
| Testing | pytest | 8.4.2 |
| Frontend | HTML5 + Vanilla CSS + JavaScript | — |
| Accelerator | Apple Silicon MPS | — |

---

*Document version: Phase 1 initial*
*Last updated: 2026-08-31*
