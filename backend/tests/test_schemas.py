"""Tests for Pydantic schemas — serialization and validation."""

from __future__ import annotations

import json

import pytest

from ai.common.schemas import (
    DensityLevel,
    DensityWindow,
    DetectionResult,
    FrameResult,
    ProcessingConfig,
    ProcessingResult,
    ProcessingStatus,
    TrackResult,
    VehicleCountSummary,
    VideoMetadata,
)


def test_video_metadata_serializes():
    """VideoMetadata must serialize to valid JSON."""
    meta = VideoMetadata(
        video_id="test-123",
        filename="video.mp4",
        width=1920,
        height=1080,
        fps=30.0,
        frame_count=900,
        duration_seconds=30.0,
        codec="avc1",
        file_size_bytes=1024 * 1024 * 50,
    )
    data = json.loads(meta.model_dump_json())
    assert data["video_id"] == "test-123"
    assert data["width"] == 1920
    assert data["fps"] == 30.0


def test_detection_result_serializes():
    """DetectionResult must serialize with all required fields."""
    det = DetectionResult(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[100.0, 100.0, 300.0, 250.0],
    )
    data = json.loads(det.model_dump_json())
    assert data["class_id"] == 2
    assert data["class_name"] == "car"
    assert data["confidence"] == 0.91
    assert len(data["bbox"]) == 4


def test_track_result_serializes():
    """TrackResult must serialize with track_id and timestamps."""
    track = TrackResult(
        track_id=17,
        class_id=2,
        class_name="car",
        confidence=0.87,
        bbox=[100.0, 100.0, 300.0, 250.0],
        first_seen_timestamp=0.5,
        last_seen_timestamp=3.2,
        frames_seen=84,
    )
    data = json.loads(track.model_dump_json())
    assert data["track_id"] == 17
    assert data["first_seen_timestamp"] == 0.5
    assert data["frames_seen"] == 84


def test_vehicle_count_summary_serializes():
    """VehicleCountSummary by_class is a dict."""
    summary = VehicleCountSummary(
        total_unique_vehicles=12,
        by_class={"car": 8, "motorcycle": 3, "bus": 1},
    )
    data = json.loads(summary.model_dump_json())
    assert data["total_unique_vehicles"] == 12
    assert data["by_class"]["car"] == 8


def test_density_window_includes_note():
    """DensityWindow must include a non-empty note field."""
    window = DensityWindow(
        window_start=0.0,
        window_end=5.0,
        unique_vehicle_count=8,
        density_level=DensityLevel.MEDIUM,
    )
    data = json.loads(window.model_dump_json())
    assert "note" in data
    assert len(data["note"]) > 0


def test_processing_result_full_structure():
    """ProcessingResult top-level JSON has required keys."""
    meta = VideoMetadata(
        video_id="test-456",
        filename="test.mp4",
        width=640,
        height=480,
        fps=30.0,
        frame_count=100,
        duration_seconds=3.33,
    )
    config = ProcessingConfig(
        device="mps",
        model_name="yolo11n.pt",
        imgsz=640,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        frame_interval=1,
        batch_size=1,
    )
    result = ProcessingResult(
        video=meta,
        processing=config,
        status=ProcessingStatus.COMPLETE,
    )
    data = json.loads(result.model_dump_json())
    assert "video" in data
    assert "processing" in data
    assert "status" in data
    assert "frames" in data
    assert "density_windows" in data


def test_no_images_in_json():
    """ProcessingResult must NOT contain base64 image data or numpy arrays."""
    result = ProcessingResult(
        video=VideoMetadata(
            video_id="img-test",
            filename="test.mp4",
            width=640,
            height=480,
            fps=30.0,
            frame_count=10,
            duration_seconds=0.33,
        ),
        processing=ProcessingConfig(
            device="cpu",
            model_name="yolo11n.pt",
            imgsz=640,
            confidence_threshold=0.25,
            iou_threshold=0.45,
            frame_interval=1,
            batch_size=1,
        ),
        status=ProcessingStatus.COMPLETE,
    )
    json_str = result.model_dump_json()
    # No base64 image data should be present
    assert "base64" not in json_str.lower()
    assert "ndarray" not in json_str.lower()


def test_density_level_values():
    """DensityLevel enum values must be exactly low/medium/high/unknown."""
    assert DensityLevel.LOW == "low"
    assert DensityLevel.MEDIUM == "medium"
    assert DensityLevel.HIGH == "high"
    assert DensityLevel.UNKNOWN == "unknown"
