"""Tests for traffic density calculation."""

from __future__ import annotations

import pytest

from ai.common.schemas import DensityLevel, TrackResult
from ai.traffic.density import DensityCalculator


def make_vehicle_track(track_id: int) -> TrackResult:
    return TrackResult(
        track_id=track_id,
        class_id=2,
        class_name="car",
        confidence=0.9,
        bbox=[100.0, 100.0, 200.0, 200.0],
        first_seen_timestamp=0.0,
        last_seen_timestamp=5.0,
        frames_seen=100,
    )


def test_density_low():
    """3 vehicles → LOW density."""
    calc = DensityCalculator(
        window_seconds=5.0,
        low_threshold=5,
        medium_threshold=15,
    )
    # 3 unique vehicles in window 0–5s
    for i in range(3):
        calc.add_frame(timestamp=1.0, tracks=[make_vehicle_track(i)])

    windows = calc.compute_windows()
    assert len(windows) == 1
    assert windows[0].unique_vehicle_count == 3
    assert windows[0].density_level == DensityLevel.LOW


def test_density_medium():
    """10 vehicles → MEDIUM density."""
    calc = DensityCalculator(
        window_seconds=5.0,
        low_threshold=5,
        medium_threshold=15,
    )
    for i in range(10):
        calc.add_frame(timestamp=2.0, tracks=[make_vehicle_track(i)])

    windows = calc.compute_windows()
    assert windows[0].unique_vehicle_count == 10
    assert windows[0].density_level == DensityLevel.MEDIUM


def test_density_high():
    """20 vehicles → HIGH density."""
    calc = DensityCalculator(
        window_seconds=5.0,
        low_threshold=5,
        medium_threshold=15,
    )
    for i in range(20):
        calc.add_frame(timestamp=3.0, tracks=[make_vehicle_track(i)])

    windows = calc.compute_windows()
    assert windows[0].unique_vehicle_count == 20
    assert windows[0].density_level == DensityLevel.HIGH


def test_multiple_windows():
    """Frames in different time windows produce separate density entries."""
    calc = DensityCalculator(
        window_seconds=5.0,
        low_threshold=5,
        medium_threshold=15,
    )
    # Window 0 (0–5s): 3 vehicles
    for i in range(3):
        calc.add_frame(timestamp=2.0, tracks=[make_vehicle_track(i)])

    # Window 1 (5–10s): 20 vehicles
    for i in range(100, 120):
        calc.add_frame(timestamp=7.0, tracks=[make_vehicle_track(i)])

    windows = calc.compute_windows()
    assert len(windows) == 2

    # Window 0
    assert windows[0].window_start == 0.0
    assert windows[0].window_end == 5.0
    assert windows[0].unique_vehicle_count == 3
    assert windows[0].density_level == DensityLevel.LOW

    # Window 1
    assert windows[1].window_start == 5.0
    assert windows[1].window_end == 10.0
    assert windows[1].unique_vehicle_count == 20
    assert windows[1].density_level == DensityLevel.HIGH


def test_same_track_id_not_double_counted():
    """
    Same vehicle appearing multiple times in one window counts as 1.
    """
    calc = DensityCalculator(
        window_seconds=5.0,
        low_threshold=5,
        medium_threshold=15,
    )
    # Same track_id=1 appears 100 times in the same window
    track = make_vehicle_track(track_id=1)
    for _ in range(100):
        calc.add_frame(timestamp=2.0, tracks=[track])

    windows = calc.compute_windows()
    assert windows[0].unique_vehicle_count == 1


def test_density_disclaimer():
    """Every density window must include the prototype disclaimer."""
    calc = DensityCalculator(window_seconds=5.0, low_threshold=5, medium_threshold=15)
    calc.add_frame(timestamp=1.0, tracks=[make_vehicle_track(1)])
    windows = calc.compute_windows()
    for w in windows:
        assert "prototype" in w.note.lower() or "not calibrated" in w.note.lower()


def test_density_invalid_thresholds():
    """Invalid thresholds must raise ValueError."""
    with pytest.raises(ValueError):
        DensityCalculator(
            window_seconds=5.0,
            low_threshold=15,
            medium_threshold=5,  # medium < low — invalid
        )


def test_density_reset():
    """After reset, compute_windows returns empty."""
    calc = DensityCalculator(window_seconds=5.0, low_threshold=5, medium_threshold=15)
    calc.add_frame(timestamp=1.0, tracks=[make_vehicle_track(1)])
    calc.reset()
    windows = calc.compute_windows()
    assert windows == []


def test_empty_video_no_windows():
    """If no frames added, compute_windows returns empty list."""
    calc = DensityCalculator(window_seconds=5.0, low_threshold=5, medium_threshold=15)
    windows = calc.compute_windows()
    assert windows == []
