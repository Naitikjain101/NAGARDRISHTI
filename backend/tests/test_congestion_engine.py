"""
Urban Watch — Tests for Phase 5E: CongestionEngine
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.common.schemas import TrackResult
from ai.traffic.congestion import CongestionEngine, CongestionWindow


def make_track(track_id: int, class_name: str = "car", ts: float = 0.0) -> TrackResult:
    return TrackResult(
        track_id=track_id, class_id=2, class_name=class_name,
        confidence=0.85, bbox=[0.0, 0.0, 100.0, 100.0],
        first_seen_timestamp=ts, last_seen_timestamp=ts, frames_seen=1,
    )


class TestCongestionEngine:
    @pytest.fixture
    def engine(self):
        return CongestionEngine(
            window_seconds=5.0,
            low_threshold=5,
            medium_threshold=15,
            severe_threshold=30,
            reference_density=50,
        )

    def test_empty_video(self, engine):
        windows = engine.compute_congestion_windows()
        assert windows == []

    def test_low_traffic(self, engine):
        for i in range(3):
            engine.add_frame(0.5, [make_track(i, ts=0.5)])
        windows = engine.compute_congestion_windows()
        assert len(windows) == 1
        assert windows[0].congestion_level == "LOW"
        assert windows[0].congestion_score < 0.15

    def test_medium_traffic(self, engine):
        tracks = [make_track(i) for i in range(10)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert windows[0].congestion_level == "MEDIUM"

    def test_high_traffic(self, engine):
        tracks = [make_track(i) for i in range(20)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert windows[0].congestion_level == "HIGH"

    def test_severe_traffic(self, engine):
        tracks = [make_track(i) for i in range(35)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert windows[0].congestion_level == "SEVERE"

    def test_congestion_score_normalized(self, engine):
        # reference_density=50, so 50 vehicles → score=1.0
        tracks = [make_track(i) for i in range(50)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert windows[0].congestion_score == 1.0

    def test_congestion_score_clamped(self, engine):
        # 100 vehicles, reference=50 → clamped to 1.0
        tracks = [make_track(i) for i in range(100)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert windows[0].congestion_score <= 1.0

    def test_by_class_tracking(self, engine):
        tracks = [
            make_track(1, "car"),
            make_track(2, "car"),
            make_track(3, "motorcycle"),
        ]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        assert "car" in windows[0].by_class
        assert "motorcycle" in windows[0].by_class

    def test_multiple_windows(self, engine):
        engine.add_frame(0.5, [make_track(1)])
        engine.add_frame(6.0, [make_track(2)])  # Second window
        windows = engine.compute_congestion_windows()
        assert len(windows) == 2

    def test_current_congestion_level_empty(self, engine):
        assert engine.current_congestion_level() == "UNKNOWN"

    def test_current_congestion_score_empty(self, engine):
        assert engine.current_congestion_score() == 0.0

    def test_reset(self, engine):
        tracks = [make_track(i) for i in range(10)]
        engine.add_frame(1.0, tracks)
        engine.reset()
        windows = engine.compute_congestion_windows()
        assert windows == []

    def test_non_vehicle_ignored(self, engine):
        """Person class is not a vehicle — should not affect congestion score."""
        person_tracks = [
            TrackResult(
                track_id=i, class_id=0, class_name="person",
                confidence=0.8, bbox=[0.0, 0.0, 50.0, 100.0],
                first_seen_timestamp=0.0, last_seen_timestamp=0.0, frames_seen=1,
            )
            for i in range(20)
        ]
        engine.add_frame(1.0, person_tracks)
        # Persons are not vehicles — DensityCalculator won't record any vehicle
        # so no window is produced (no vehicle frames tracked)
        # Congestion level should remain UNKNOWN (no data)
        level = engine.current_congestion_level()
        score = engine.current_congestion_score()
        assert level == "UNKNOWN"
        assert score == 0.0

    def test_window_to_dict(self, engine):
        tracks = [make_track(1)]
        engine.add_frame(1.0, tracks)
        windows = engine.compute_congestion_windows()
        d = windows[0].to_dict()
        assert "congestion_score" in d
        assert "congestion_level" in d
        assert "by_class" in d
        assert "note" in d
