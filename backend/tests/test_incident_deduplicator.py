"""
Urban Watch — Tests for Phase 5D: IncidentDeduplicator

Tests spatial grouping, merge behavior, and passthrough of non-confirmed events.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.pothole.deduplicator import IncidentDeduplicator


# ---------------------------------------------------------------------------
# Fake event stubs
# ---------------------------------------------------------------------------

@dataclass
class FakeEvent:
    event_id: int = 1
    representative_bbox: List[float] = field(default_factory=lambda: [100.0, 200.0, 200.0, 300.0])
    max_confidence: float = 0.80
    total_detections: int = 10
    status: object = None

    def __post_init__(self):
        if self.status is None:
            self.status = _FakeStatus("confirmed")


class _FakeStatus:
    def __init__(self, val: str):
        self.value = val


def make_confirmed(event_id, bbox, confidence=0.80):
    return FakeEvent(event_id=event_id, representative_bbox=bbox, max_confidence=confidence)


def make_suppressed(event_id, bbox):
    e = FakeEvent(event_id=event_id, representative_bbox=bbox)
    e.status = _FakeStatus("suppressed")
    return e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIncidentDeduplicator:
    @pytest.fixture
    def dedup(self):
        return IncidentDeduplicator(center_distance_threshold=0.08)

    def test_empty_events(self, dedup):
        result = dedup.deduplicate([], 640, 480)
        assert result == []

    def test_single_event_passthrough(self, dedup):
        events = [make_confirmed(1, [100.0, 200.0, 200.0, 300.0])]
        result = dedup.deduplicate(events, 640, 480)
        assert len(result) == 1

    def test_two_far_events_not_merged(self, dedup):
        """Events far apart → no merge."""
        e1 = make_confirmed(1, [10.0, 10.0, 50.0, 50.0])      # top-left
        e2 = make_confirmed(2, [550.0, 400.0, 620.0, 460.0])   # bottom-right
        result = dedup.deduplicate([e1, e2], 640, 480)
        confirmed = [r for r in result if r.status.value == "confirmed"]
        assert len(confirmed) == 2

    def test_two_nearby_events_merged(self, dedup):
        """Events very close → merge into 1."""
        # Centers: (150, 250) and (155, 255) → distance ≈ 0.009 (normalized)
        e1 = make_confirmed(1, [100.0, 200.0, 200.0, 300.0])
        e2 = make_confirmed(2, [105.0, 205.0, 205.0, 305.0])
        result = dedup.deduplicate([e1, e2], 640, 480)
        confirmed = [r for r in result if r.status.value == "confirmed"]
        assert len(confirmed) == 1

    def test_suppressed_events_pass_through(self, dedup):
        """Suppressed events are never merged — pass through unchanged."""
        e1 = make_suppressed(1, [100.0, 200.0, 200.0, 300.0])
        e2 = make_suppressed(2, [105.0, 205.0, 205.0, 305.0])
        result = dedup.deduplicate([e1, e2], 640, 480)
        suppressed = [r for r in result if r.status.value == "suppressed"]
        assert len(suppressed) == 2

    def test_mixed_confirmed_and_suppressed(self, dedup):
        """Only confirmed events are merged; suppressed pass through."""
        e_confirmed = make_confirmed(1, [100.0, 200.0, 200.0, 300.0])
        e_suppressed = make_suppressed(2, [105.0, 205.0, 205.0, 305.0])
        result = dedup.deduplicate([e_confirmed, e_suppressed], 640, 480)
        assert len(result) == 2  # 1 confirmed + 1 suppressed

    def test_merged_event_has_highest_confidence(self, dedup):
        """After merge, base event is the one with highest confidence."""
        e1 = make_confirmed(1, [100.0, 200.0, 200.0, 300.0], confidence=0.90)
        e2 = make_confirmed(2, [105.0, 205.0, 205.0, 305.0], confidence=0.60)
        result = dedup.deduplicate([e1, e2], 640, 480)
        confirmed = [r for r in result if r.status.value == "confirmed"]
        assert len(confirmed) == 1
        assert confirmed[0].max_confidence == 0.90

    def test_normalized_center_valid(self):
        center = IncidentDeduplicator._normalized_center(
            [100.0, 200.0, 200.0, 300.0], 640, 480
        )
        assert center is not None
        assert abs(center[0] - 0.234) < 0.01  # (150/640)
        assert abs(center[1] - 0.521) < 0.01  # (250/480)

    def test_normalized_center_invalid_bbox(self):
        center = IncidentDeduplicator._normalized_center(None, 640, 480)
        assert center is None

    def test_euclidean_distance(self):
        dist = IncidentDeduplicator._euclidean((0.0, 0.0), (0.3, 0.4))
        assert abs(dist - 0.5) < 0.001

    def test_three_events_two_nearby_one_far(self, dedup):
        e1 = make_confirmed(1, [100.0, 200.0, 200.0, 300.0])
        e2 = make_confirmed(2, [105.0, 205.0, 205.0, 305.0])  # near e1
        e3 = make_confirmed(3, [500.0, 50.0, 600.0, 150.0])   # far from both
        result = dedup.deduplicate([e1, e2, e3], 640, 480)
        confirmed = [r for r in result if r.status.value == "confirmed"]
        assert len(confirmed) == 2  # e1+e2 merged, e3 alone
