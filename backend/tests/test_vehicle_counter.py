"""Tests for vehicle counting logic."""

from __future__ import annotations

import pytest

from ai.common.schemas import TrackResult
from ai.traffic.vehicle_counter import VehicleCounter


def make_track(
    track_id: int,
    class_name: str,
    class_id: int = 2,
    confidence: float = 0.9,
) -> TrackResult:
    return TrackResult(
        track_id=track_id,
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bbox=[100.0, 100.0, 200.0, 200.0],
        first_seen_timestamp=0.0,
        last_seen_timestamp=1.0,
        frames_seen=10,
    )


def test_unique_vehicles_not_summed():
    """
    THE CORE TEST:
    A vehicle appearing in 5 frames must count as 1, not 5.
    """
    counter = VehicleCounter()

    # Same track (ID=1, class=car) appears in 5 frames
    for _ in range(5):
        counter.update([make_track(track_id=1, class_name="car")])

    summary = counter.get_summary()
    assert summary.total_unique_vehicles == 1
    assert summary.by_class["car"] == 1


def test_two_vehicles_two_ids():
    """Two different vehicles (IDs 1 and 2) count as 2."""
    counter = VehicleCounter()
    counter.update([
        make_track(track_id=1, class_name="car"),
        make_track(track_id=2, class_name="car"),
    ])
    # Same two tracks appear in next frame
    counter.update([
        make_track(track_id=1, class_name="car"),
        make_track(track_id=2, class_name="car"),
    ])

    summary = counter.get_summary()
    assert summary.total_unique_vehicles == 2
    assert summary.by_class["car"] == 2


def test_mixed_classes():
    """Counts per vehicle class are correct."""
    counter = VehicleCounter()
    counter.update([
        make_track(track_id=1, class_name="car", class_id=2),
        make_track(track_id=2, class_name="motorcycle", class_id=3),
        make_track(track_id=3, class_name="bus", class_id=5),
        make_track(track_id=4, class_name="truck", class_id=7),
        make_track(track_id=5, class_name="bicycle", class_id=1),
    ])

    summary = counter.get_summary()
    assert summary.total_unique_vehicles == 5
    assert summary.by_class.get("car", 0) == 1
    assert summary.by_class.get("motorcycle", 0) == 1
    assert summary.by_class.get("bus", 0) == 1
    assert summary.by_class.get("truck", 0) == 1
    assert summary.by_class.get("bicycle", 0) == 1


def test_person_not_counted_as_vehicle():
    """Persons (track_id=99, class='person') must NOT be in vehicle count."""
    counter = VehicleCounter()
    person_track = TrackResult(
        track_id=99,
        class_id=0,
        class_name="person",
        confidence=0.88,
        bbox=[50.0, 50.0, 100.0, 200.0],
        first_seen_timestamp=0.0,
        last_seen_timestamp=1.0,
        frames_seen=5,
    )
    counter.update([person_track])

    summary = counter.get_summary()
    assert summary.total_unique_vehicles == 0
    assert "person" not in summary.by_class


def test_counter_reset():
    """After reset, counts return to zero."""
    counter = VehicleCounter()
    counter.update([make_track(track_id=1, class_name="car")])
    counter.reset()
    summary = counter.get_summary()
    assert summary.total_unique_vehicles == 0
    assert summary.by_class == {}


def test_get_active_vehicle_ids_in_frame():
    """get_active_vehicle_ids_in_frame returns vehicle IDs in current frame."""
    counter = VehicleCounter()
    tracks = [
        make_track(track_id=1, class_name="car"),
        make_track(track_id=2, class_name="truck", class_id=7),
        TrackResult(
            track_id=99, class_id=0, class_name="person", confidence=0.9,
            bbox=[0.0, 0.0, 50.0, 100.0],
            first_seen_timestamp=0.0, last_seen_timestamp=0.5, frames_seen=1,
        ),
    ]
    active = counter.get_active_vehicle_ids_in_frame(tracks)
    assert active == {1, 2}
    assert 99 not in active  # person excluded
