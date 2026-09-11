"""
Urban Watch — Traffic Density Calculator

Computes rolling-window traffic density from unique track IDs.

IMPORTANT DISCLAIMER:
This is a PROTOTYPE traffic-density metric based on tracked vehicle counts.
It is NOT calibrated traffic engineering data.
Thresholds are configurable and must be documented in PHASE_1_REPORT.md.

Algorithm:
1. Divide video timeline into windows of DENSITY_WINDOW_SECONDS
2. For each window, collect all unique vehicle track IDs seen in that window
3. Count unique IDs → unique_vehicle_count
4. Apply configurable thresholds to classify: LOW / MEDIUM / HIGH
"""

from __future__ import annotations

import logging
from collections import defaultdict

from ai.common.schemas import DensityLevel, DensityWindow, TrackResult
from ai.detection.classes import is_vehicle_class

logger = logging.getLogger(__name__)

# Disclaimer text attached to every density window
DENSITY_DISCLAIMER = (
    "Prototype traffic-density classification based on tracked vehicle counts. "
    "NOT calibrated traffic engineering data. "
    "Thresholds are configurable: see backend/ai/common/config.py."
)


class DensityCalculator:
    """
    Computes rolling-window traffic density.

    Usage:
        calc = DensityCalculator(
            window_seconds=5.0,
            low_threshold=5,
            medium_threshold=15,
        )
        # Feed frames in order
        calc.add_frame(timestamp, tracks)
        # Get result
        windows = calc.compute_windows()
    """

    def __init__(
        self,
        window_seconds: float = 5.0,
        low_threshold: int = 5,
        medium_threshold: int = 15,
        video_duration: float = 0.0,
    ) -> None:
        """
        Parameters
        ----------
        window_seconds : float
            Duration of each rolling window in seconds.
        low_threshold : int
            Unique vehicle count threshold for LOW density.
            < low_threshold → LOW
            [low_threshold, medium_threshold) → MEDIUM
            >= medium_threshold → HIGH
        medium_threshold : int
            Unique vehicle count threshold for MEDIUM/HIGH boundary.
        video_duration : float
            Total video duration in seconds. Used to define final window.
        """
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if low_threshold < 0 or medium_threshold <= low_threshold:
            raise ValueError(
                "Thresholds must be: 0 <= low_threshold < medium_threshold"
            )

        self.window_seconds = window_seconds
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.video_duration = video_duration

        # Map: window_index → set of unique vehicle track IDs
        self._window_vehicle_ids: dict[int, set[int]] = defaultdict(set)
        # Maximum timestamp seen
        self._max_timestamp: float = 0.0

    def add_frame(
        self,
        timestamp: float,
        tracks: list[TrackResult],
    ) -> None:
        """
        Add a frame's tracking data to the density calculation.

        Parameters
        ----------
        timestamp : float
            Video timestamp in seconds.
        tracks : list[TrackResult]
            Tracked objects in this frame.
        """
        window_idx = int(timestamp / self.window_seconds)

        for track in tracks:
            if is_vehicle_class(track.class_name):
                self._window_vehicle_ids[window_idx].add(track.track_id)

        self._max_timestamp = max(self._max_timestamp, timestamp)

    def compute_windows(self) -> list[DensityWindow]:
        """
        Compute density windows from all added frames.

        Returns
        -------
        list[DensityWindow]
            One entry per window, sorted by window_start.
        """
        if not self._window_vehicle_ids:
            return []

        max_window_idx = max(self._window_vehicle_ids.keys())
        windows: list[DensityWindow] = []

        for window_idx in range(max_window_idx + 1):
            window_start = window_idx * self.window_seconds
            window_end = window_start + self.window_seconds

            vehicle_ids = self._window_vehicle_ids.get(window_idx, set())
            count = len(vehicle_ids)
            level = self._classify(count)

            windows.append(DensityWindow(
                window_start=round(window_start, 3),
                window_end=round(window_end, 3),
                unique_vehicle_count=count,
                density_level=level,
                note=DENSITY_DISCLAIMER,
            ))

        logger.info(
            "Density: %d windows, levels=%s",
            len(windows),
            [w.density_level.value for w in windows],
        )
        return windows

    def _classify(self, count: int) -> DensityLevel:
        """
        Classify a vehicle count into a density level.

        Thresholds are from configuration, not hardcoded.
        """
        if count < self.low_threshold:
            return DensityLevel.LOW
        elif count < self.medium_threshold:
            return DensityLevel.MEDIUM
        else:
            return DensityLevel.HIGH

    def reset(self) -> None:
        """Reset state. Call between videos."""
        self._window_vehicle_ids.clear()
        self._max_timestamp = 0.0
