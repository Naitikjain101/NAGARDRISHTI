"""
Urban Watch — Pothole Video Spatio-Temporal Event Tracker

Tracks individual pothole instances across consecutive video frames.
Solves the duplicate count problem:
- Distinguishes 1 physical pothole appearing for 50 frames from 50 separate potholes.
- Measures temporal stability quantitatively.
- Filters out single-frame transient noise / false blips.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ai.pothole.config import (
    POTHOLE_FRAME_GAP_TOLERANCE,
    POTHOLE_MIN_EVENT_FRAMES,
    POTHOLE_TRACKING_IOU_THRESHOLD,
)
from ai.pothole.schemas import PotholeDetection, PotholeEvent

logger = logging.getLogger(__name__)


class PotholeEventTracker:
    """Tracks physical potholes across time to group frame detections into events."""

    def __init__(
        self,
        iou_threshold: float = POTHOLE_TRACKING_IOU_THRESHOLD,
        frame_gap_tolerance: int = POTHOLE_FRAME_GAP_TOLERANCE,
        min_event_frames: int = POTHOLE_MIN_EVENT_FRAMES,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.frame_gap_tolerance = frame_gap_tolerance
        self.min_event_frames = min_event_frames

        self._active_events: List[Dict] = []
        self._completed_events: List[PotholeEvent] = []
        self._next_event_id: int = 1

    def update(
        self,
        frame_index: int,
        timestamp: float,
        detections: List[PotholeDetection],
    ) -> List[int]:
        """
        Update tracker with detections from a frame.

        Returns
        -------
        List[int]
            Active event IDs present in this frame.
        """
        matched_event_ids: set[int] = set()
        active_ids_in_frame: List[int] = []

        for det in detections:
            best_iou = 0.0
            best_event = None

            for ev in self._active_events:
                if ev["id"] in matched_event_ids:
                    continue
                if frame_index - ev["last_frame"] <= self.frame_gap_tolerance:
                    iou = self._compute_iou(det.bbox, ev["last_bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_event = ev

            if best_iou >= self.iou_threshold and best_event is not None:
                best_event["last_frame"] = frame_index
                best_event["last_timestamp"] = timestamp
                best_event["last_bbox"] = det.bbox
                best_event["detections_count"] += 1
                best_event["max_confidence"] = max(best_event["max_confidence"], det.confidence)
                best_event["sum_confidence"] += det.confidence
                best_event["bboxes"].append(det.bbox)
                matched_event_ids.add(best_event["id"])
                active_ids_in_frame.append(best_event["id"])
            else:
                # New candidate event
                new_event = {
                    "id": self._next_event_id,
                    "first_frame": frame_index,
                    "first_timestamp": timestamp,
                    "last_frame": frame_index,
                    "last_timestamp": timestamp,
                    "last_bbox": det.bbox,
                    "detections_count": 1,
                    "max_confidence": det.confidence,
                    "sum_confidence": det.confidence,
                    "bboxes": [det.bbox],
                }
                self._next_event_id += 1
                self._active_events.append(new_event)
                matched_event_ids.add(new_event["id"])
                active_ids_in_frame.append(new_event["id"])

        # Flush dead events (exceeded gap tolerance)
        still_active: List[Dict] = []
        for ev in self._active_events:
            if frame_index - ev["last_frame"] > self.frame_gap_tolerance:
                self._finalize_event(ev)
            else:
                still_active.append(ev)
        self._active_events = still_active

        return active_ids_in_frame

    def finalize(self) -> List[PotholeEvent]:
        """Finalize all remaining active events at end of video stream."""
        for ev in self._active_events:
            self._finalize_event(ev)
        self._active_events.clear()
        return self._completed_events

    def get_confirmed_events(self) -> List[PotholeEvent]:
        """Return only persistent, confirmed pothole events (>= min_event_frames)."""
        return [e for e in self._completed_events if e.is_confirmed]

    def _finalize_event(self, ev_dict: Dict) -> None:
        span_frames = ev_dict["last_frame"] - ev_dict["first_frame"] + 1
        count = ev_dict["detections_count"]
        stability = count / span_frames if span_frames > 0 else 1.0
        mean_conf = ev_dict.get("sum_confidence", ev_dict["max_confidence"]) / count if count > 0 else 0.0

        # Representative bbox: median coordinates across detection lifespan
        bboxes = ev_dict["bboxes"]
        rep_bbox = [
            round(float(np.median([b[0] for b in bboxes])), 2),
            round(float(np.median([b[1] for b in bboxes])), 2),
            round(float(np.median([b[2] for b in bboxes])), 2),
            round(float(np.median([b[3] for b in bboxes])), 2),
        ] if bboxes else ev_dict["last_bbox"]

        event = PotholeEvent(
            event_id=ev_dict["id"],
            first_seen_frame=ev_dict["first_frame"],
            first_seen_timestamp=round(ev_dict["first_timestamp"], 3),
            last_seen_frame=ev_dict["last_frame"],
            last_seen_timestamp=round(ev_dict["last_timestamp"], 3),
            total_detections=count,
            span_frames=span_frames,
            stability_score=round(stability, 4),
            max_confidence=round(ev_dict["max_confidence"], 4),
            mean_confidence=round(mean_conf, 4),
            representative_bbox=rep_bbox,
            is_confirmed=(count >= self.min_event_frames),
        )
        self._completed_events.append(event)

    @staticmethod
    def _compute_iou(box1: List[float], box2: List[float]) -> float:
        xA, yA = max(box1[0], box2[0]), max(box1[1], box2[1])
        xB, yB = min(box1[2], box2[2]), min(box1[3], box2[3])
        inter = max(0.0, xB - xA) * max(0.0, yB - yA)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0.0 else 0.0


import numpy as np
