"""
Urban Watch — Vehicle Counter

Counts unique vehicles using persistent track IDs.

CRITICAL RULE:
Vehicle count = number of unique track_id values across frames.
Do NOT sum raw detection counts.

Example:
    Frame 1: car ID=1, car ID=2
    Frame 2: car ID=1, car ID=2
    Frame 3: car ID=1, car ID=3

    Correct count: 3 unique vehicles (IDs 1, 2, 3)
    Wrong count: 6 (summing detections across frames)
"""

from __future__ import annotations

import logging
from collections import defaultdict

from ai.common.schemas import TrackResult, VehicleCountSummary
from ai.detection.classes import VEHICLE_CLASSES, is_vehicle_class

logger = logging.getLogger(__name__)


class VehicleCounter:
    """
    Counts unique vehicles across a video using track IDs.

    Usage:
        counter = VehicleCounter()
        for frame_tracks in all_frame_tracks:
            counter.update(frame_tracks)
        summary = counter.get_summary()
    """

    def __init__(self) -> None:
        # Set of unique track IDs per vehicle class
        self._track_ids_by_class: dict[str, set[int]] = defaultdict(set)
        # All unique vehicle track IDs (any vehicle class)
        self._all_vehicle_track_ids: set[int] = set()
        # All unique track IDs (including non-vehicle like person)
        self._all_track_ids: set[int] = set()

    def update(self, tracks: list[TrackResult]) -> None:
        """
        Update counts with tracks from one frame.
        Ensures each track ID is counted under exactly ONE class (its most recent stable class).
        """
        for track in tracks:
            self._all_track_ids.add(track.track_id)

            if is_vehicle_class(track.class_name):
                # Remove this track_id from any other class sets it might have been in
                for cls, ids in self._track_ids_by_class.items():
                    if cls != track.class_name and track.track_id in ids:
                        ids.remove(track.track_id)
                
                self._track_ids_by_class[track.class_name].add(track.track_id)
                self._all_vehicle_track_ids.add(track.track_id)

    def get_summary(self) -> VehicleCountSummary:
        """
        Return the total unique vehicle count summary.

        Returns
        -------
        VehicleCountSummary
            Total unique vehicles and per-class breakdown.
        """
        by_class = {
            cls: len(ids)
            for cls, ids in sorted(self._track_ids_by_class.items())
        }

        summary = VehicleCountSummary(
            total_unique_vehicles=len(self._all_vehicle_track_ids),
            by_class=by_class,
        )

        logger.info(
            "Vehicle count: %d unique vehicles — %s",
            summary.total_unique_vehicles,
            by_class,
        )
        return summary

    def get_active_vehicle_ids_in_frame(
        self, tracks: list[TrackResult]
    ) -> set[int]:
        """
        Return the set of active vehicle track IDs in a single frame.
        Used by density calculator for per-window counting.
        """
        return {
            t.track_id
            for t in tracks
            if is_vehicle_class(t.class_name)
        }

    def reset(self) -> None:
        """Reset all counts. Call between videos."""
        self._track_ids_by_class.clear()
        self._all_vehicle_track_ids.clear()
        self._all_track_ids.clear()

    @property
    def total_unique_vehicles(self) -> int:
        return len(self._all_vehicle_track_ids)

    @property
    def total_unique_objects(self) -> int:
        """All unique objects including non-vehicles (e.g., persons)."""
        return len(self._all_track_ids)
