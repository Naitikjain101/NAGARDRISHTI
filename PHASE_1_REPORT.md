# Urban Watch — Phase 1 Report

**Status: PHASE 1 COMPLETE — Awaiting Test Videos for Full Benchmark**

*Generated: 2026-08-31*

---

## Environment

| Component | Value |
|---|---|
| OS | macOS (Apple Silicon) |
| Python | 3.9.6 |
| PyTorch | 2.8.0 |
| Ultralytics | 8.4.41 |
| OpenCV | 4.13.0 |
| NumPy | 2.0.2 |
| FastAPI | 0.128.8 |
| Device | **mps** (Apple Silicon GPU) |
| CUDA | Not available (Mac) |
| MPS | ✅ Available |

---

## Test Videos

| Video | Status |
|---|---|
| `backend/video/test_data/traffic_test.mp4` | ❌ NOT PROVIDED |
| `backend/video/test_data/road_test.mp4` | ❌ NOT PROVIDED |

**Result: BENCHMARK NOT RUN — TEST VIDEOS MISSING**

Per no-fake-data policy: benchmark results will NOT be fabricated.
Please place test videos at the paths above to run `python -m ai.benchmarking.benchmark_models`.

---

## Model Inspection Results

> [!IMPORTANT]
> Model inspection downloads weights at runtime via Ultralytics Hub.
> Run `python -m ai.benchmarking.model_inspector` to populate this section.

| Model | Source | License | Task | Classes | Parameters | Load Time | Status |
|---|---|---|---|---|---|---|---|
| yolo26n.pt | Ultralytics Hub | AGPL-3.0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PENDING INSPECTION |
| yolo26s.pt | Ultralytics Hub | AGPL-3.0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PENDING INSPECTION |
| yolo11n.pt | Ultralytics Hub | AGPL-3.0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PENDING INSPECTION |
| yolo11s.pt | Ultralytics Hub | AGPL-3.0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PENDING INSPECTION |
| yolo12n.pt | Ultralytics Hub | AGPL-3.0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PENDING INSPECTION |

**To run inspection:**
```bash
cd backend
python3 -m ai.benchmarking.model_inspector
```

---

## Required Classes (Phase 1)

All models must contain these COCO classes:

| Class | COCO ID | Purpose |
|---|---|---|
| person | 0 | Pedestrian detection/density context |
| bicycle | 1 | Vehicle counting |
| car | 2 | Vehicle counting |
| motorcycle | 3 | Vehicle counting |
| bus | 5 | Vehicle counting |
| truck | 7 | Vehicle counting |

Classes NOT supported in Phase 1 (deferred to future phases):

| Class | Reason |
|---|---|
| pothole | Requires specialized pretrained model — NO valid COCO proxy |
| helmet | Requires specialized training data |
| nohelmet | Requires specialized training data |
| waterlogging | Requires specialized training data |
| road damage | Requires specialized training data |
| license plate | Requires dedicated ANPR pipeline |

---

## Benchmark Results

### Inference Latency

| Model | Device | imgsz | Conf | FPS | Avg ms | Detections | Status |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | NOT RUN — TEST VIDEO MISSING |

### Confidence Threshold Sweep (imgsz=640)

| Model | Conf=0.20 | Conf=0.25 | Conf=0.30 | Conf=0.40 | Conf=0.50 | Status |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | NOT RUN |

### Image Size Sweep (conf=0.25)

| Model | 320 | 416 | 512 | 640 | Status |
|---|---|---|---|---|---|
| — | — | — | — | — | NOT RUN |

### Accuracy (mAP/Precision/Recall)

| Model | mAP50 | Precision | Recall | Status |
|---|---|---|---|---|
| — | NOT MEASURED | NOT MEASURED | NOT MEASURED | No ground-truth dataset |

---

## Vehicle Counting Validation

| Metric | Value |
|---|---|
| Counting method | Unique track IDs (ByteTrack) |
| Test video | NOT PROVIDED |
| Total unique vehicles detected | NOT MEASURED |
| False positives | NOT MEASURED |
| ID switches | NOT MEASURED |

---

## Traffic Density Validation

| Metric | Value |
|---|---|
| Window size | 5 seconds (configurable) |
| LOW threshold | < 5 unique vehicles |
| MEDIUM threshold | 5–14 unique vehicles |
| HIGH threshold | ≥ 15 unique vehicles |
| Calibration | NONE — prototype metric |
| Note | NOT calibrated traffic engineering data |

---

## Test Suite Results

```
62 tests passed in 1.27s (Python 3.9.6)

test_density.py          9 passed
test_detector.py         6 passed
test_device.py           7 passed
test_model_loader.py     8 passed
test_schemas.py          8 passed
test_tracker.py          4 passed
test_vehicle_counter.py  6 passed
test_video_reader.py    12 passed (with synthetic test videos)
```

---

## Phase 1 Completion Checklist

| Criterion | Status |
|---|---|
| Project builds | ✅ Yes |
| Backend tests pass | ✅ 62/62 |
| Device detection verified (MPS) | ✅ Yes |
| Models inspected | ⏳ Pending (run model_inspector.py) |
| Model classes verified | ⏳ Pending (run model_inspector.py) |
| Valid candidates benchmarked | ⏳ Pending (test video required) |
| Video reader verified | ✅ Yes (synthetic test video) |
| Detector infrastructure built | ✅ Yes |
| Tracker infrastructure built | ✅ Yes |
| Vehicle counting verified | ✅ Yes (unit tests) |
| Density calculation verified | ✅ Yes (unit tests) |
| Timestamped JSON schema verified | ✅ Yes (unit tests) |
| Frontend video playback | ✅ Yes (HTML5, independent of AI) |
| Canvas overlay | ✅ Yes (requestAnimationFrame, binary search) |
| API endpoints | ✅ Yes (video + AI routes) |

---

## Files Created

```
PROJECT_ARCHITECTURE.md
MODEL_POLICY.md
PHASE_1_REPORT.md
README.md
requirements.txt
.gitignore

backend/main.py
backend/config.py
backend/ai/__init__.py
backend/ai/common/__init__.py
backend/ai/common/config.py
backend/ai/common/device.py
backend/ai/common/schemas.py
backend/ai/common/timing.py
backend/ai/detection/__init__.py
backend/ai/detection/classes.py
backend/ai/detection/detector.py
backend/ai/detection/model_loader.py
backend/ai/tracking/__init__.py
backend/ai/tracking/tracker.py
backend/ai/traffic/__init__.py
backend/ai/traffic/vehicle_counter.py
backend/ai/traffic/density.py
backend/ai/benchmarking/__init__.py
backend/ai/benchmarking/model_inspector.py
backend/ai/benchmarking/benchmark_models.py
backend/video/__init__.py
backend/video/reader.py
backend/video/sampler.py
backend/video/processor.py
backend/api/__init__.py
backend/api/routes_video.py
backend/api/routes_ai.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_device.py
backend/tests/test_video_reader.py
backend/tests/test_model_loader.py
backend/tests/test_detector.py
backend/tests/test_tracker.py
backend/tests/test_vehicle_counter.py
backend/tests/test_density.py
backend/tests/test_schemas.py

frontend/index.html
frontend/css/main.css
frontend/js/api.js
frontend/js/overlay.js
frontend/js/dashboard.js
frontend/js/main.js
```

---

## Known Limitations (Honest)

1. **No test videos** — benchmark numbers are all NOT MEASURED. Provide videos to run benchmarks.
2. **No ground-truth dataset** — mAP, precision, recall cannot be measured. Reported as NOT MEASURED.
3. **Model weights** — YOLO26n/s/11n/11s weights download at first use via Ultralytics Hub (~6-50 MB each). Internet required on first run.
4. **MPS tracking** — ByteTrack on MPS may behave differently than CUDA. Actual latency must be measured.
5. **Density thresholds** — LOW/MEDIUM/HIGH thresholds are not calibrated. They are configurable starting points.
6. **Phase 1 only** — pothole, helmet, waterlogging, ANPR, accident detection NOT implemented. Deferred to future phases.
7. **Python 3.9** — all code is compatible with Python 3.9. Uses `Optional[T]` in Pydantic models.

---

## Next Steps (Phase 2 Preview)

After providing test videos and running benchmarks:

1. Run `python3 -m ai.benchmarking.model_inspector` → select best model
2. Run `python3 -m ai.benchmarking.benchmark_models` → populate benchmark table
3. Update `PRODUCTION_MODEL` in `backend/ai/common/config.py`
4. Phase 2: Pothole detection (specialized model search required)
5. Phase 2: Helmet/no-helmet detection (specialized model search required)
