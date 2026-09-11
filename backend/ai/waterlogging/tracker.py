"""
Urban Watch — Waterlogging Spatio-Temporal Event Tracker
Tracks waterlogging detections across consecutive video frames to measure persistence and stability.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ai.waterlogging.config import (
    WATERLOGGING_FRAME_GAP_TOLERANCE,
    WATERLOGGING_MIN_EVENT_FRAMES,
    WATERLOGGING_TRACKING_IOU_THRESHOLD,
)
from ai.waterlogging.schemas import WaterloggingDetection
from ai.unified.schemas import UnifiedPotholeEvent

logger = logging.getLogger(__name__)


class WaterloggingEventTracker:
    """Tracks physical waterlogging instances across time."""

    def __init__(
        self,
        iou_threshold: float = WATERLOGGING_TRACKING_IOU_THRESHOLD,
        frame_gap_tolerance: int = WATERLOGGING_FRAME_GAP_TOLERANCE,
        min_event_frames: int = WATERLOGGING_MIN_EVENT_FRAMES,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.frame_gap_tolerance = frame_gap_tolerance
        self.min_event_frames = min_event_frames

        self._active_events: List[Dict] = []
        self._completed_events: List[Dict] = []
        self._next_event_id: int = 1

    def update(
        self,
        frame_index: int,
        timestamp: float,
        detections: List[WaterloggingDetection],
    ) -> List[int]:
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
                
                # Keep tracking mask and area ratio
                best_event["last_polygon"] = det.polygon
                best_event["max_area_ratio"] = max(best_event.get("max_area_ratio", 0.0), det.area_ratio)

                matched_event_ids.add(best_event["id"])
                active_ids_in_frame.append(best_event["id"])
            else:
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
                    "last_polygon": det.polygon,
                    "max_area_ratio": det.area_ratio,
                }
                self._next_event_id += 1
                self._active_events.append(new_event)
                matched_event_ids.add(new_event["id"])
                active_ids_in_frame.append(new_event["id"])

        self._retire_stale_events(frame_index)
        return active_ids_in_frame

    def _retire_stale_events(self, current_frame: int) -> None:
        active = []
        for ev in self._active_events:
            if current_frame - ev["last_frame"] > self.frame_gap_tolerance:
                span = ev["last_frame"] - ev["first_frame"] + 1
                if ev["detections_count"] >= self.min_event_frames:
                    self._completed_events.append(ev)
            else:
                active.append(ev)
        self._active_events = active

    def get_events(self, flush: bool = False) -> List[Dict]:
        events = list(self._completed_events)
        if flush:
            for ev in self._active_events:
                if ev["detections_count"] >= self.min_event_frames:
                    events.append(ev)
            self._completed_events.clear()
            self._active_events.clear()
        
        # Calculate stability for all returned events
        for ev in events:
            span = ev["last_frame"] - ev["first_frame"] + 1
            ev["stability_score"] = ev["detections_count"] / max(1, span)
            ev["mean_confidence"] = ev["sum_confidence"] / max(1, ev["detections_count"])
            
            # Representative bbox (median coordinates)
            x1s = [b[0] for b in ev["bboxes"]]
            y1s = [b[1] for b in ev["bboxes"]]
            x2s = [b[2] for b in ev["bboxes"]]
            y2s = [b[3] for b in ev["bboxes"]]
            import statistics
            ev["representative_bbox"] = [
                statistics.median(x1s),
                statistics.median(y1s),
                statistics.median(x2s),
                statistics.median(y2s),
            ]

        return events

    def _compute_iou(self, box1: List[float], box2: List[float]) -> float:
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if inter == 0.0:
            return 0.0

        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

        return inter / (area1 + area2 - inter + 1e-6)
