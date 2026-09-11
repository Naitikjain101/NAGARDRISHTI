"""
Urban Watch — Phase 5E: CongestionEngine

Extends the existing DensityCalculator with:
1. SEVERE congestion level (beyond HIGH)
2. congestion_score [0, 1] for heatmap generation
3. CongestionLevel enum alignment with Phase 5 GIS schemas

IMPORTANT:
- This does NOT replace DensityCalculator.
- It is a wrapper/extension used by the Phase 5 unified pipeline.
- All thresholds are configurable in ai/common/config.py.
- congestion_score is NOT calibrated traffic engineering data.
  It is a normalized operational indicator.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ai.common.config import (
    DENSITY_WINDOW_SECONDS,
    TRAFFIC_LOW_THRESHOLD,
    TRAFFIC_MEDIUM_THRESHOLD,
    TRAFFIC_SEVERE_THRESHOLD,
    CONGESTION_REFERENCE_DENSITY,
)
from ai.common.schemas import TrackResult, DensityWindow
from ai.traffic.density import DensityCalculator
from ai.detection.classes import is_vehicle_class

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extended Density Level (adds SEVERE)
# ---------------------------------------------------------------------------

CONGESTION_LEVELS = {
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "SEVERE": "SEVERE",
    "UNKNOWN": "UNKNOWN",
}


class CongestionWindow:
    """
    Extended density window with congestion_score and SEVERE level.

    This is the Phase 5 extension of DensityWindow.
    """

    def __init__(
        self,
        window_start: float,
        window_end: float,
        unique_vehicle_count: int,
        density_level: str,
        congestion_score: float,
        congestion_level: str,
        by_class: Optional[Dict[str, int]] = None,
        note: str = "",
    ) -> None:
        self.window_start = window_start
        self.window_end = window_end
        self.unique_vehicle_count = unique_vehicle_count
        self.density_level = density_level
        self.congestion_score = congestion_score
        self.congestion_level = congestion_level
        self.by_class = by_class or {}
        self.note = note

    def to_dict(self) -> dict:
        return {
            "window_start": round(self.window_start, 3),
            "window_end": round(self.window_end, 3),
            "unique_vehicle_count": self.unique_vehicle_count,
            "density_level": self.density_level,
            "congestion_score": round(self.congestion_score, 4),
            "congestion_level": self.congestion_level,
            "by_class": self.by_class,
            "note": self.note,
        }


class CongestionEngine:
    """
    Phase 5 Traffic Congestion Engine.

    Extends DensityCalculator with SEVERE level and normalized congestion score.

    Usage:
        engine = CongestionEngine()
        for frame_tracks in ...:
            engine.add_frame(timestamp, tracks)
        windows = engine.compute_congestion_windows()
        current = engine.current_congestion_level()
    """

    CONGESTION_NOTE = (
        "Prototype traffic-congestion classification based on tracked vehicle counts. "
        "NOT calibrated traffic engineering data. "
        "congestion_score is a normalized [0,1] operational indicator only. "
        "Thresholds configurable in backend/ai/common/config.py."
    )

    def __init__(
        self,
        window_seconds: float = DENSITY_WINDOW_SECONDS,
        low_threshold: int = TRAFFIC_LOW_THRESHOLD,
        medium_threshold: int = TRAFFIC_MEDIUM_THRESHOLD,
        severe_threshold: int = TRAFFIC_SEVERE_THRESHOLD,
        reference_density: int = CONGESTION_REFERENCE_DENSITY,
    ) -> None:
        self.window_seconds = window_seconds
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.severe_threshold = severe_threshold
        self.reference_density = reference_density

        # Delegate basic density to existing DensityCalculator
        self._density_calc = DensityCalculator(
            window_seconds=window_seconds,
            low_threshold=low_threshold,
            medium_threshold=medium_threshold,
        )

        # Phase 5 additions: per-window per-class tracking
        from collections import defaultdict
        self._window_class_ids: Dict[int, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
        self._max_seen: int = 0

    def add_frame(self, timestamp: float, tracks: List[TrackResult]) -> None:
        """Add a frame's tracking data."""
        self._density_calc.add_frame(timestamp, tracks)

        window_idx = int(timestamp / self.window_seconds)
        for track in tracks:
            if is_vehicle_class(track.class_name):
                self._window_class_ids[window_idx][track.class_name].add(track.track_id)
                count = sum(len(ids) for ids in self._window_class_ids[window_idx].values())
                if count > self._max_seen:
                    self._max_seen = count

    def compute_congestion_windows(self) -> List[CongestionWindow]:
        """Compute extended congestion windows."""
        density_windows = self._density_calc.compute_windows()
        congestion_windows = []

        for dw in density_windows:
            window_idx = int(dw.window_start / self.window_seconds)
            class_ids = self._window_class_ids.get(window_idx, {})
            by_class = {cls: len(ids) for cls, ids in sorted(class_ids.items())}
            count = dw.unique_vehicle_count

            congestion_score = self._compute_score(count)
            congestion_level = self._classify_extended(count)

            congestion_windows.append(CongestionWindow(
                window_start=dw.window_start,
                window_end=dw.window_end,
                unique_vehicle_count=count,
                density_level=dw.density_level.value,
                congestion_score=congestion_score,
                congestion_level=congestion_level,
                by_class=by_class,
                note=self.CONGESTION_NOTE,
            ))

        return congestion_windows

    def current_congestion_level(self) -> str:
        """Return the congestion level for the most recent window."""
        windows = self.compute_congestion_windows()
        if not windows:
            return "UNKNOWN"
        return windows[-1].congestion_level

    def current_congestion_score(self) -> float:
        """Return the normalized congestion score for the most recent window."""
        windows = self.compute_congestion_windows()
        if not windows:
            return 0.0
        return windows[-1].congestion_score

    def _compute_score(self, unique_vehicle_count: int) -> float:
        """Normalize vehicle count to [0, 1] congestion score."""
        if self.reference_density <= 0:
            return 0.0
        return min(unique_vehicle_count / self.reference_density, 1.0)

    def _classify_extended(self, count: int) -> str:
        """Extended classification including SEVERE."""
        if count < self.low_threshold:
            return "LOW"
        elif count < self.medium_threshold:
            return "MEDIUM"
        elif count < self.severe_threshold:
            return "HIGH"
        else:
            return "SEVERE"

    def reset(self) -> None:
        """Reset state for next video."""
        self._density_calc.reset()
        self._window_class_ids.clear()
        self._max_seen = 0
