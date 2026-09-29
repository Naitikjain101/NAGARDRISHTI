"""
Urban Watch — pytest fixtures and configuration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure backend is in Python path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_bgr_frame():
    """A 640×480 BGR frame filled with a gradient (simulates a real frame)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add some structure so it's not completely blank
    frame[:, :, 2] = np.linspace(0, 255, 640, dtype=np.uint8)  # red gradient
    return frame


@pytest.fixture
def tiny_bgr_frame():
    """A tiny 64×64 frame for fast tests."""
    return np.zeros((64, 64, 3), dtype=np.uint8)


@pytest.fixture
def sample_detections():
    """Sample DetectionResult list for testing downstream components."""
    from ai.common.schemas import DetectionResult
    return [
        DetectionResult(class_id=2, class_name="car", confidence=0.91, bbox=[100, 100, 300, 250]),
        DetectionResult(class_id=2, class_name="car", confidence=0.85, bbox=[400, 150, 600, 300]),
        DetectionResult(class_id=3, class_name="motorcycle", confidence=0.78, bbox=[50, 200, 150, 320]),
    ]


@pytest.fixture
def sample_tracks():
    """Sample TrackResult list for testing vehicle counter and density."""
    from ai.common.schemas import TrackResult
    return [
        TrackResult(
            track_id=1, class_id=2, class_name="car", confidence=0.91,
            bbox=[100, 100, 300, 250], first_seen_timestamp=0.0,
            last_seen_timestamp=0.5, frames_seen=10,
        ),
        TrackResult(
            track_id=2, class_id=2, class_name="car", confidence=0.85,
            bbox=[400, 150, 600, 300], first_seen_timestamp=0.0,
            last_seen_timestamp=0.5, frames_seen=8,
        ),
        TrackResult(
            track_id=3, class_id=3, class_name="motorcycle", confidence=0.78,
            bbox=[50, 200, 150, 320], first_seen_timestamp=0.1,
            last_seen_timestamp=0.5, frames_seen=5,
        ),
    ]
