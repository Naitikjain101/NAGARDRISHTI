"""Tests for DetectionResult schema and bbox validity."""

from __future__ import annotations

import pytest

from ai.common.schemas import DetectionResult


def test_detection_result_valid():
    """Valid detection must create without error."""
    d = DetectionResult(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[100.0, 100.0, 300.0, 250.0],
    )
    assert d.class_id == 2
    assert d.class_name == "car"
    assert d.confidence == 0.91


def test_detection_result_bbox_length():
    """bbox must have exactly 4 elements."""
    with pytest.raises(Exception):
        DetectionResult(
            class_id=2,
            class_name="car",
            confidence=0.91,
            bbox=[100.0, 100.0, 300.0],  # only 3 elements
        )


def test_detection_result_confidence_range():
    """confidence must be in [0, 1]."""
    with pytest.raises(Exception):
        DetectionResult(
            class_id=2,
            class_name="car",
            confidence=1.5,  # out of range
            bbox=[100.0, 100.0, 300.0, 250.0],
        )

    with pytest.raises(Exception):
        DetectionResult(
            class_id=2,
            class_name="car",
            confidence=-0.1,  # negative
            bbox=[100.0, 100.0, 300.0, 250.0],
        )


def test_bbox_valid_within_frame():
    """bbox_valid() returns True when bbox is within frame bounds."""
    d = DetectionResult(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[100.0, 100.0, 300.0, 250.0],
    )
    assert d.bbox_valid(frame_width=640, frame_height=480) is True


def test_bbox_valid_out_of_bounds():
    """bbox_valid() returns False when bbox exceeds frame dimensions."""
    d = DetectionResult(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[100.0, 100.0, 700.0, 250.0],  # x2=700 > width=640
    )
    assert d.bbox_valid(frame_width=640, frame_height=480) is False


def test_bbox_valid_degenerate():
    """x2 > x1 and y2 > y1 must be required."""
    d = DetectionResult(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[300.0, 100.0, 100.0, 250.0],  # x1 > x2
    )
    assert d.bbox_valid(frame_width=640, frame_height=480) is False


def test_bbox_coordinates_are_original_space(sample_detections):
    """Bboxes from sample_detections fixture must be valid within 640x480."""
    for det in sample_detections:
        assert det.bbox_valid(640, 480)
