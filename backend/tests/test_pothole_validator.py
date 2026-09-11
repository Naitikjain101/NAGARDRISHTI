"""
Urban Watch — Tests for Phase 5C: PotholeValidator

Tests multi-signal scoring, edge cases, and weight behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.pothole.validator import PotholeValidator, PotholeValidatorConfig, _clamp


# ---------------------------------------------------------------------------
# Test event stub (matches UnifiedPotholeEvent interface)
# ---------------------------------------------------------------------------

@dataclass
class FakeEvent:
    event_id: int = 1
    mean_confidence: float = 0.75
    max_confidence: float = 0.85
    total_detections: int = 10
    span_frames: int = 15
    representative_bbox: List[float] = field(default_factory=lambda: [100.0, 300.0, 200.0, 380.0])
    suppression_reason: Optional[str] = None
    status: str = "confirmed"


# ---------------------------------------------------------------------------
# Clamp helper
# ---------------------------------------------------------------------------

class TestClamp:
    def test_clamp_normal(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below(self):
        assert _clamp(-0.5) == 0.0

    def test_clamp_above(self):
        assert _clamp(1.5) == 1.0


# ---------------------------------------------------------------------------
# PotholeValidator core
# ---------------------------------------------------------------------------

class TestPotholeValidator:
    @pytest.fixture
    def validator(self):
        return PotholeValidator()

    def test_score_returns_float_in_range(self, validator):
        event = FakeEvent()
        score, signals = validator.score(event, frame_width=640, frame_height=480)
        assert 0.0 <= score <= 1.0

    def test_score_strong_event(self, validator):
        """High confidence + many frames + stable bbox → high score."""
        event = FakeEvent(
            mean_confidence=0.90,
            max_confidence=0.95,
            total_detections=30,
            span_frames=40,
            representative_bbox=[200.0, 300.0, 280.0, 360.0],
        )
        score, signals = validator.score(event, 640, 480)
        # Should score well above minimum threshold
        assert score >= 0.40, f"Expected strong event to score >= 0.40, got {score}"

    def test_score_weak_event(self, validator):
        """Single detection, tiny bbox → low score."""
        event = FakeEvent(
            mean_confidence=0.26,
            max_confidence=0.26,
            total_detections=1,
            span_frames=1,
            representative_bbox=[100.0, 200.0, 102.0, 202.0],  # tiny bbox
        )
        score, signals = validator.score(event, 640, 480)
        # Weak event should score lower
        assert score < 0.60, f"Expected weak event to score < 0.60, got {score}"

    def test_vehicle_overlap_penalty_applied(self, validator):
        """Events under vehicles get penalty."""
        event_normal = FakeEvent(suppression_reason=None)
        event_overlap = FakeEvent(suppression_reason="vehicle_overlap_detected")

        score_normal, _ = validator.score(event_normal, 640, 480)
        score_overlap, signals_overlap = validator.score(event_overlap, 640, 480)

        assert signals_overlap.has_vehicle_overlap is True
        assert score_overlap < score_normal

    def test_score_signals_structure(self, validator):
        """Signals object has all expected fields."""
        event = FakeEvent()
        score, signals = validator.score(event, 640, 480)

        assert hasattr(signals, "model_confidence")
        assert hasattr(signals, "temporal_score")
        assert hasattr(signals, "spatial_score")
        assert hasattr(signals, "geometry_score")
        assert hasattr(signals, "frequency_score")
        assert hasattr(signals, "has_vehicle_overlap")
        assert hasattr(signals, "composite_score")
        assert hasattr(signals, "is_above_threshold")

    def test_score_no_bboxes_uses_neutral_spatial(self, validator):
        """When bboxes not provided, spatial score defaults to neutral 0.5."""
        event = FakeEvent()
        score, signals = validator.score(event, 640, 480, bboxes=None)
        # Spatial signal (weight 0.20) contributes 0.5 * 0.20 = 0.10
        # Score should still be valid
        assert 0.0 <= score <= 1.0

    def test_custom_weights(self):
        """Custom weights are applied correctly."""
        config = PotholeValidatorConfig(
            weight_model_confidence=1.0,
            weight_temporal=0.0,
            weight_spatial=0.0,
            weight_geometry=0.0,
            weight_frequency=0.0,
            vehicle_overlap_penalty=0.0,
        )
        validator = PotholeValidator(config=config)
        event = FakeEvent(mean_confidence=0.80)
        score, signals = validator.score(event, 640, 480)
        # Only model confidence contributes: score ≈ 0.80
        assert abs(score - 0.80) < 0.05

    def test_to_dict(self, validator):
        """Signals to_dict() produces serializable output."""
        event = FakeEvent()
        _, signals = validator.score(event, 640, 480)
        d = signals.to_dict()
        assert isinstance(d, dict)
        assert "composite_score" in d
        assert "is_above_threshold" in d

    def test_temporal_score_single_detection(self, validator):
        """Single detection → near-zero temporal score."""
        ts = validator._temporal_score(total_detections=1, span_frames=1)
        assert ts == 0.0

    def test_temporal_score_persistent(self, validator):
        """Many detections over many frames → high temporal score."""
        ts = validator._temporal_score(total_detections=20, span_frames=25)
        assert ts > 0.5

    def test_geometry_score_zero_bbox(self, validator):
        """Degenerate bbox → score 0."""
        gs = validator._geometry_score([0.0, 0.0, 0.0, 0.0], 640, 480)
        assert gs == 0.0

    def test_geometry_score_reasonable_bbox(self, validator):
        """Normal pothole bbox → reasonable geometry score."""
        # 100x80 bbox in 640x480 frame = area_ratio ≈ 0.026
        gs = validator._geometry_score([200.0, 300.0, 300.0, 380.0], 640, 480)
        assert gs > 0.3

    def test_spatial_score_stable(self, validator):
        """Same bbox across all frames → maximum stability."""
        bboxes = [[100.0, 200.0, 200.0, 280.0]] * 10
        ss = validator._spatial_score(bboxes, 640, 480)
        assert ss >= 0.99

    def test_spatial_score_jumping(self, validator):
        """Bbox jumping wildly → low stability."""
        bboxes = [
            [0.0, 0.0, 50.0, 50.0],
            [550.0, 400.0, 640.0, 480.0],
            [100.0, 100.0, 200.0, 200.0],
            [400.0, 300.0, 500.0, 380.0],
        ]
        ss = validator._spatial_score(bboxes, 640, 480)
        assert ss < 0.6
