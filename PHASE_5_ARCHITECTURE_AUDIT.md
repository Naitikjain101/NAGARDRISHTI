# PHASE 5 ARCHITECTURE AUDIT

**Audit Date**: 2026-09-01  
**Status**: READ-ONLY — No production code was modified during this audit.  
**Baseline**: 81/81 tests passing before any Phase 5 changes.

---

## 1. Current Architecture Overview

```
Nagardristi2.0/
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Server config (paths, CORS, etc.)
│   ├── ai/
│   │   ├── common/             # Shared config, schemas, device, timing
│   │   ├── detection/          # YOLO inference + class filter
│   │   ├── pothole/            # Pothole detector + tracker + config
│   │   │   └── weights/        # pothole_yolov8_peterhdd.pt [PRODUCTION]
│   │   ├── tracking/           # ByteTracker wrapper
│   │   ├── traffic/            # Density calculator + vehicle counter
│   │   ├── unified/            # Full pipeline: processor + events + filters
│   │   └── benchmarking/       # Cross-model ablation benchmark
│   ├── api/                    # FastAPI route handlers
│   ├── video/                  # Reader + sampler + Phase1 processor
│   ├── tests/                  # 81 tests (ALL PASSING)
│   └── results/                # JSON output files
└── frontend/
    ├── index.html              # Existing HTML/CSS/JS frontend (Phase 3 era)
    ├── css/main.css
    └── js/
```

## 2. Current AI Models

### Vehicle Detection — PRODUCTION
- **Model**: yolo11n.pt (YOLO11 Nano, COCO-pretrained)
- **Location**: backend/yolo11n.pt
- **Classes**: car, motorcycle, bus, truck, bicycle, person
- **Pipeline**: model.track() via ByteTracker wrapper

### Pothole Detection — PRODUCTION
- **Model**: pothole_yolov8_peterhdd.pt (YOLOv8m, 21.4 MB)
- **Source**: Hugging Face peterhdd/pothole-detection-yolov8
- **Classes**: {0: "pothole"} (single-class)
- **Phase 4B Baseline**: 690 raw → 31 confirmed events on road_test.mp4

### Helmet Detection — ABSENT
- **best_roadx.pt** was NOT FOUND on disk
- Classes claimed: helmet, licenseplate, motorcyclist, nohelmet
- Action: Build configurable HelmetDetector scaffold; gracefully disabled if model absent

## 3. Pothole Pipeline (Phase 4B/5A State)

RAW DETECTION → RoadROIFilter → GeometryFilter → PotholeEventTracker (IoU) → VehicleInteractionSuppressor → UnifiedPotholeEvent

Phase 5A Baseline (road_test.mp4):
- Raw: 690 | Rejected ROI: 251 | Rejected Geometry: 30 | Rejected Temporal: 13 | Confirmed: 31

## 4. Existing API Routes

Working:
- POST /api/video/upload
- GET  /api/video/{id}/metadata
- GET  /api/video/{id}/stream
- POST /api/ai/unified/process/{id}
- GET  /api/ai/unified/status/{id}
- GET  /api/ai/unified/results/{id}
- GET  /api/ai/device
- GET  /api/health

Mock only: GET /api/events

Missing (Phase 5 targets):
- GET /api/incidents, /api/incidents/{id}
- GET /api/traffic/current, /history, /heatmap
- GET /api/road-conditions
- GET /api/system/status, /api/system/device

## 5. Reuse Decisions

REUSE (unchanged):
- ai/pothole/detector.py, tracker.py, config.py, schemas.py
- ai/tracking/tracker.py (ByteTracker)
- ai/traffic/density.py, vehicle_counter.py
- ai/unified/filters.py, interaction.py, severity.py
- ai/common/device.py, timing.py
- api/routes_video.py, routes_ai.py
- video/reader.py, sampler.py
- All 81 existing tests

EXTEND (additive changes only):
- ai/common/config.py — add Phase5 validator weights
- ai/common/schemas.py — add GPS, GIS fields as Optional
- ai/unified/events.py — add PotholeValidator call
- ai/unified/processor.py — add helmet pipeline

BUILD NEW:
- ai/gis/ — GIS schemas (Incident, Vehicle, TrafficWindow, RoadSegment)
- ai/pothole/validator.py — PotholeValidator multi-signal scoring
- ai/traffic/congestion.py — CongestionEngine (extends DensityCalculator)
- api/routes_incidents.py, routes_traffic.py, routes_system.py
- db/ — SQLite via SQLAlchemy
- frontend/ — React+TypeScript+Vite complete rebuild

## 6. Potential Regressions & Mitigations

| Risk | Mitigation |
|------|-----------|
| PotholeValidator changes raise/lower event count | Benchmark before+after; document all weight changes |
| helmet model absent → crash | Graceful disable: log warning, skip if not found |
| Schema changes break existing 81 tests | Run tests after every change; never delete tests |
| CORS issues with Vite dev server (port 5173) | Add 5173 to CORS_ORIGINS in config.py |
| SQLite locking under concurrent requests | Single-writer pattern; thread lock for BG tasks |

## 7. Phase 4 Baseline (Verified, Unmodified)

| Metric | road_test.mp4 | traffic_test.mp4 |
|--------|--------------|-----------------|
| Total Frames | 1,005 | 902 |
| Processing FPS | 28.4 | 8.1 |
| Raw Pothole Detections | 690 | 37 |
| Rejected (ROI) | 251 | 0 |
| Rejected (Geometry) | 30 | 0 |
| Rejected (Temporal) | 13 | 1 |
| Rejected (Vehicle Overlap) | 0 | 5 |
| Confirmed Pothole Events | 31 | 7 |
| Tests Passing | 81/81 | — |

*Source: PHASE_5_ROAD_AWARE_INTELLIGENCE.md, MODEL_COMPARISON_REPORT.md*
*No production code was modified during this audit.*
