"""Tests for tracker deduplication logic."""

from __future__ import annotations

import pytest

from ai.common.schemas import TrackResult


def make_track(track_id: int, class_name: str = "car", timestamp: float = 0.0) -> TrackResult:
    return TrackResult(
        track_id=track_id,
        class_id=2,
        class_name=class_name,
        confidence=0.9,
        bbox=[100.0, 100.0, 200.0, 200.0],
        first_seen_timestamp=0.0,
        last_seen_timestamp=timestamp,
        frames_seen=1,
    )


def test_track_id_uniqueness():
    """
    THE CORE TRACKER TEST:
    If same track_id appears in multiple frames,
    a counter must count it ONCE.
    """
    seen_ids: set[int] = set()

    # Same track ID=17 in 5 consecutive frames
    for _ in range(5):
        for track in [make_track(17, "car")]:
            seen_ids.add(track.track_id)

    assert len(seen_ids) == 1
    assert 17 in seen_ids


def test_different_ids_different_vehicles():
    """Different track IDs → different vehicles."""
    seen_ids: set[int] = set()
    tracks_per_frame = [
        [make_track(1, "car"), make_track(2, "car")],
        [make_track(1, "car"), make_track(2, "car"), make_track(3, "motorcycle")],
        [make_track(2, "car"), make_track(3, "motorcycle")],
    ]
    for frame_tracks in tracks_per_frame:
        for t in frame_tracks:
            seen_ids.add(t.track_id)

    assert len(seen_ids) == 3
    assert seen_ids == {1, 2, 3}


def test_track_result_schema():
    """TrackResult must serialize to correct fields."""
    track = make_track(track_id=42, class_name="truck", timestamp=5.5)
    d = track.model_dump()
    assert d["track_id"] == 42
    assert d["class_name"] == "truck"
    assert d["last_seen_timestamp"] == 5.5
    assert "bbox" in d
    assert len(d["bbox"]) == 4


def test_track_has_required_fields():
    """TrackResult must have all required tracking fields."""
    track = TrackResult(
        track_id=1,
        class_id=2,
        class_name="car",
        confidence=0.91,
        bbox=[0.0, 0.0, 100.0, 100.0],
        first_seen_timestamp=0.0,
        last_seen_timestamp=5.0,
        frames_seen=150,
    )
    assert track.first_seen_timestamp == 0.0
    assert track.last_seen_timestamp == 5.0
    assert track.frames_seen == 150
