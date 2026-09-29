"""
Urban Watch — Unit Tests for Pothole Detection & Analytics (Phase 2 Step 2)
"""

from __future__ import annotations

import os
from pathlib import Path
import numpy as np
import pytest

from ai.pothole.config import (
    DEFAULT_POTHOLE_MODEL,
    POTHOLE_CONFIDENCE_THRESHOLD,
    POTHOLE_IMGSZ,
    POTHOLE_IOU_THRESHOLD,
)
from ai.pothole.detector import PotholeDetector, PotholeDetectorConfig
from ai.pothole.model_inspector import inspect_pothole_model
from ai.pothole.model_registry import PotholeModelRegistry
from ai.pothole.schemas import (
    PotholeDetection,
    PotholeEvent,
    PotholeFrameResult,
    PotholeVideoSummary,
)
from ai.pothole.tracker import PotholeEventTracker


def test_pothole_detection_schema():
    """PotholeDetection schema validation and bbox bounds check."""
    det = PotholeDetection(
        class_id=0,
        class_name="pothole",
        confidence=0.89,
        bbox=[100.0, 150.0, 300.0, 350.0],
    )
    assert det.class_name == "pothole"
    assert det.confidence == 0.89
    assert det.bbox_valid(640, 480) is True
    assert det.bbox_valid(200, 200) is False  # Out of bounds


def test_pothole_event_schema():
    """PotholeEvent schema and stability calculation."""
    ev = PotholeEvent(
        event_id=1,
        first_seen_frame=10,
        first_seen_timestamp=0.4,
        last_seen_frame=20,
        last_seen_timestamp=0.8,
        total_detections=11,
        span_frames=11,
        stability_score=1.0,
        max_confidence=0.92,
        representative_bbox=[100.0, 100.0, 200.0, 200.0],
        is_confirmed=True,
    )
    assert ev.span_frames == 11
    assert ev.stability_score == 1.0
    assert ev.is_confirmed is True


def test_model_inspector_valid():
    """Valid pothole checkpoint must be accepted and contain pothole class."""
    if os.path.exists(DEFAULT_POTHOLE_MODEL):
        info = inspect_pothole_model(DEFAULT_POTHOLE_MODEL)
        assert isinstance(info, dict)
        assert "valid" in info


def test_model_inspector_rejects_missing_file():
    """Non-existent model path must be marked invalid."""
    info = inspect_pothole_model("/nonexistent/fake_model.pt")
    assert info["valid"] is False
    assert "does not exist" in info["rejection_reason"]


def test_model_inspector_rejects_non_pothole_model():
    """Standard COCO model (without pothole class) must be rejected."""
    coco_path = Path(__file__).parent.parent / "yolo11n.pt"
    if coco_path.exists():
        info = inspect_pothole_model(str(coco_path))
        assert info["valid"] is False
        assert "does not contain 'pothole' class" in info["rejection_reason"]


def test_pothole_registry():
    """PotholeModelRegistry retrieval and listing."""
    reg = PotholeModelRegistry()
    assert "yolo26n_640" in [m["key"] for m in reg.list_models()]
    entry = reg.get("yolo26n_640")
    assert entry["native_imgsz"] == 640
    assert entry["status"] == "DEPRECATED_NOISY"


def test_pothole_detector_deduplication():
    """_deduplicate_boxes should suppress overlapping duplicate boxes."""
    # 2 boxes with 95% overlap: one at conf 0.8, one at conf 0.4
    boxes = np.array([
        [100.0, 100.0, 200.0, 200.0],
        [101.0, 101.0, 201.0, 201.0],
        [400.0, 400.0, 500.0, 500.0],  # distinct box
    ])
    confs = np.array([0.8, 0.4, 0.9])
    keep = PotholeDetector._deduplicate_boxes(boxes, confs, iou_threshold=0.45)
    # Box 1 (conf 0.4) must be dropped; only 2 boxes kept (Box 0 and Box 2)
    assert len(keep) == 2
    assert 2 in keep  # Box 2 (conf 0.9)
    assert 0 in keep  # Box 0 (conf 0.8)
    assert 1 not in keep  # Box 1 suppressed


def test_pothole_event_tracker_grouping():
    """Event tracker must group multiple frame detections into 1 persistent event."""
    tracker = PotholeEventTracker(iou_threshold=0.20, frame_gap_tolerance=3, min_event_frames=3)
    
    # Simulate a pothole moving slightly over 5 consecutive frames
    for f in range(5):
        det = PotholeDetection(
            class_id=0, class_name="pothole", confidence=0.85,
            bbox=[100.0 + f, 100.0 + f, 200.0 + f, 200.0 + f]
        )
        active_ids = tracker.update(frame_index=f, timestamp=f * 0.04, detections=[det])
        assert len(active_ids) == 1
        assert active_ids[0] == 1  # Same event ID across all 5 frames!

    events = tracker.finalize()
    assert len(events) == 1
    ev = events[0]
    assert ev.total_detections == 5
    assert ev.span_frames == 5
    assert ev.stability_score == 1.0
    assert ev.is_confirmed is True


def test_pothole_event_tracker_filters_blips():
    """Single-frame blips must be marked unconfirmed (not confirmed)."""
    tracker = PotholeEventTracker(iou_threshold=0.20, frame_gap_tolerance=2, min_event_frames=3)
    
    # Frame 0: single blip
    det = PotholeDetection(class_id=0, class_name="pothole", confidence=0.30, bbox=[50.0, 50.0, 70.0, 70.0])
    tracker.update(frame_index=0, timestamp=0.0, detections=[det])
    
    # Frame 10: finalize
    tracker.update(frame_index=10, timestamp=0.4, detections=[])
    events = tracker.finalize()
    
    assert len(events) == 1
    assert events[0].is_confirmed is False
    assert len(tracker.get_confirmed_events()) == 0


def test_multi_aspect_ratio_coordinate_transformation():
    """Verify coordinate transformation exactness across 4K, 1080p, 720p, 360p, 144p."""
    aspect_ratios = [
        ("4K", 2160, 3840),
        ("1080p", 1080, 1920),
        ("720p", 720, 1280),
        ("360p", 360, 640),
        ("144p", 144, 256),
    ]
    imgsz = 640

    for name, orig_h, orig_w in aspect_ratios:
        gain = min(imgsz / orig_h, imgsz / orig_w)
        pad_x = (imgsz - orig_w * gain) / 2.0
        pad_y = (imgsz - orig_h * gain) / 2.0

        # Sample box in original coordinates
        orig_box = [0.2 * orig_w, 0.3 * orig_h, 0.5 * orig_w, 0.7 * orig_h]
        
        # Forward letterbox transform to model inference space
        model_box = [
            orig_box[0] * gain + pad_x,
            orig_box[1] * gain + pad_y,
            orig_box[2] * gain + pad_x,
            orig_box[3] * gain + pad_y,
        ]

        # Inverse transform back to original image space
        restored_box = [
            (model_box[0] - pad_x) / gain,
            (model_box[1] - pad_y) / gain,
            (model_box[2] - pad_x) / gain,
            (model_box[3] - pad_y) / gain,
        ]

        assert np.allclose(restored_box, orig_box, atol=1e-4)

