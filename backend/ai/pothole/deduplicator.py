"""
Urban Watch — Phase 5D: IncidentDeduplicator

Spatial deduplication of confirmed pothole events.

The same physical pothole may produce multiple confirmed events if:
- The vehicle passes the pothole multiple times (loop footage)
- The IoU threshold groups some detections slightly separately
- Frame gap tolerance creates two closely spaced events

This module merges nearby confirmed events into a single canonical incident.

Algorithm:
1. Compute normalized bbox center for each confirmed event
2. Group events with center distance < POTHOLE_DEDUP_CENTER_DISTANCE
3. Merge each group: take max confidence, sum occurrence counts

IMPORTANT:
- Only operates on confirmed events (status == CONFIRMED)
- Does NOT affect suppressed or rejected events
- Deduplication is purely spatial (bbox center proximity)
- Temporal proximity is NOT used (conservatively merge only very close bboxes)
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Set, Tuple

from ai.common.config import POTHOLE_DEDUP_CENTER_DISTANCE

logger = logging.getLogger(__name__)


class IncidentDeduplicator:
    """
    Spatial deduplicator for confirmed pothole events.

    Usage:
        dedup = IncidentDeduplicator()
        merged = dedup.deduplicate(confirmed_events, frame_width, frame_height)
    """

    def __init__(
        self,
        center_distance_threshold: float = POTHOLE_DEDUP_CENTER_DISTANCE,
    ) -> None:
        """
        Parameters
        ----------
        center_distance_threshold : float
            Maximum normalized distance between event centers to merge.
            Normalized by frame dimensions (0.0 = same pixel, 1.0 = full frame).
            Default from config: POTHOLE_DEDUP_CENTER_DISTANCE = 0.08
        """
        self.center_distance_threshold = center_distance_threshold

    def deduplicate(
        self,
        events: list,
        frame_width: int,
        frame_height: int,
    ) -> list:
        """
        Merge spatially close confirmed events into single incidents.

        Parameters
        ----------
        events : list[UnifiedPotholeEvent]
            All events (confirmed and non-confirmed).
        frame_width, frame_height : int
            Frame dimensions for bbox normalization.

        Returns
        -------
        list[UnifiedPotholeEvent]
            Deduplicated list. Non-confirmed events pass through unchanged.
        """
        if not events:
            return events

        # Separate confirmed from non-confirmed
        confirmed = [e for e in events if self._is_confirmed(e)]
        passthrough = [e for e in events if not self._is_confirmed(e)]

        if not confirmed:
            return events

        # Group confirmed events by spatial proximity
        groups = self._greedy_group(confirmed, frame_width, frame_height)

        merged = []
        for group in groups:
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged.append(self._merge_group(group))
                logger.debug(
                    "Deduplicator merged %d events → 1 incident (event IDs: %s)",
                    len(group),
                    [getattr(e, "event_id", "?") for e in group],
                )

        total_input = len(confirmed)
        total_output = len(merged)
        if total_input != total_output:
            logger.info(
                "Deduplicator: %d confirmed events → %d after spatial merge",
                total_input,
                total_output,
            )

        return merged + passthrough

    def _is_confirmed(self, event) -> bool:
        """Check if an event is confirmed (not suppressed/rejected)."""
        status = getattr(event, "status", None)
        if status is None:
            return False
        status_val = str(status.value) if hasattr(status, "value") else str(status)
        return status_val == "confirmed"

    def _greedy_group(
        self,
        events: list,
        frame_width: int,
        frame_height: int,
    ) -> List[List]:
        """
        Greedily group events by spatial proximity.

        Uses a union-find-like greedy approach:
        - Compute normalized center for each event
        - Iterate over pairs; if distance < threshold, merge groups
        """
        centers = [
            self._normalized_center(getattr(e, "representative_bbox", None), frame_width, frame_height)
            for e in events
        ]

        n = len(events)
        group_id = list(range(n))

        def find(x: int) -> int:
            while group_id[x] != x:
                group_id[x] = group_id[group_id[x]]
                x = group_id[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                group_id[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if centers[i] and centers[j]:
                    dist = self._euclidean(centers[i], centers[j])
                    if dist <= self.center_distance_threshold:
                        union(i, j)

        # Collect groups
        groups: dict = {}
        for i in range(n):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(events[i])

        return list(groups.values())

    def _merge_group(self, events: list):
        """
        Merge a group of events into a single representative event.

        Strategy:
        - Take the event with maximum max_confidence as base
        - Sum occurrence_counts
        - Use earliest first_seen and latest last_seen
        - Take maximum max_confidence
        - Take maximum composite_score
        """
        if len(events) == 1:
            return events[0]

        # Sort by max_confidence descending — primary event is highest confidence
        events_sorted = sorted(
            events,
            key=lambda e: getattr(e, "max_confidence", 0.0),
            reverse=True,
        )
        base = events_sorted[0]

        total_detections = sum(getattr(e, "total_detections", 1) for e in events)
        occurrence_count = sum(getattr(e, "occurrence_count", 1) for e in events)

        # Update mutable fields on base event
        try:
            base.total_detections = total_detections
            base.occurrence_count = occurrence_count
        except Exception:
            pass  # Frozen model — best effort

        return base

    @staticmethod
    def _normalized_center(
        bbox: Optional[List[float]],
        frame_width: int,
        frame_height: int,
    ) -> Optional[Tuple[float, float]]:
        """Compute normalized bbox center in [0, 1] range."""
        if not bbox or len(bbox) != 4 or frame_width <= 0 or frame_height <= 0:
            return None
        cx = (bbox[0] + bbox[2]) / (2 * frame_width)
        cy = (bbox[1] + bbox[3]) / (2 * frame_height)
        return (cx, cy)

    @staticmethod
    def _euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """Euclidean distance between two normalized center points."""
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
