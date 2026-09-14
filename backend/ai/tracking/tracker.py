"""
Urban Watch — ByteTrack Multi-Object Tracker with Precision Upgrades

Architecture:
  YOLO Detections
        ↓
  Smart Geometric Duplicate Suppression
        ↓
  ByteTrack Association
        ↓
  Temporal Class Stabilization (Rolling history of 10 observations)
        ↓
  Track Results (with stabilized classes & diagnostic metadata)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker

from ai.common.config import (
    CONFIDENCE_THRESHOLD,
    INFERENCE_IMGSZ,
    IOU_THRESHOLD,
    VEHICLE_CLASS_HISTORY_SIZE,
    VEHICLE_CROSS_CLASS_IOMIN,
    VEHICLE_CROSS_CLASS_IOU,
    VEHICLE_SAME_CLASS_IOU,
)
from ai.common.schemas import TrackResult
from ai.common.timing import FrameTimer, timer
from ai.detection.vehicle_suppression import (
    SuppressionDiagnostics,
    VehicleDuplicateSuppressor,
)
from ai.detection.classes import to_canonical_class

logger = logging.getLogger(__name__)


class TrackerArgs:
    """Default ByteTrack parameters."""

    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.6
    track_buffer: int = 30
    match_thresh: float = 0.8
    fuse_score: bool = True
    gmc_method: str = "sparseOptFlow"
    proximity_thresh: float = 0.5
    appearance_thresh: float = 0.25
    with_reid: bool = False


@dataclass
class TrackState:
    """Internal state for a single active track."""

    track_id: int
    raw_class_id: int
    raw_class: str
    stabilized_class_id: int
    stabilized_class: str
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    frames_seen: int = 1
    last_bbox: list[float] = field(default_factory=list)
    last_confidence: float = 0.0
    class_history: list[tuple[str, int, float]] = field(default_factory=list)

    # Sustained evidence tracking for class switching
    candidate_class_id: Optional[int] = None
    candidate_class: Optional[str] = None
    candidate_frames: int = 0

    @property
    def class_id(self) -> int:
        """Backward compatibility for existing code expecting class_id."""
        return self.stabilized_class_id

    @property
    def class_name(self) -> str:
        """Backward compatibility for existing code expecting class_name."""
        return self.stabilized_class


def stabilize_class(
    state: TrackState,
    min_frames: int = 5,
    conf_margin: float = 1.0
) -> Tuple[str, int]:
    """
    Stabilize class over a rolling window of recent observations.
    Uses confidence- and recency-weighted majority voting.
    Requires sustained evidence (min_frames and conf_margin) to switch the active stabilized class.
    """
    history = state.class_history
    if not history:
        return "unknown", -1

    if len(history) == 1:
        return history[0][0], history[0][1]

    weights: dict[str, float] = defaultdict(float)
    id_map: dict[str, int] = {}
    n = len(history)

    for i, (c_name, c_id, conf) in enumerate(history):
        id_map[c_name] = c_id
        # Recency weight: slightly increases weight for recent observations
        recency_factor = 1.0 + 0.15 * (i / max(1, n - 1))
        weights[c_name] += float(conf) * recency_factor

    best_class = max(weights.items(), key=lambda item: item[1])[0]
    best_id = id_map[best_class]
    
    current_stab_name = state.stabilized_class
    
    # If the voting winner is still the current stabilized class, reset candidate and keep it
    if best_class == current_stab_name:
        state.candidate_class_id = None
        state.candidate_class = None
        state.candidate_frames = 0
        return current_stab_name, state.stabilized_class_id
        
    # There's a new winner in the vote. Check if it wins by the confidence margin.
    score_diff = weights[best_class] - weights.get(current_stab_name, 0.0)
    if score_diff >= conf_margin:
        if state.candidate_class_id == best_id:
            state.candidate_frames += 1
        else:
            state.candidate_class_id = best_id
            state.candidate_class = best_class
            state.candidate_frames = 1
            
        if state.candidate_frames >= min_frames:
            # Switch successfully!
            state.candidate_class_id = None
            state.candidate_class = None
            state.candidate_frames = 0
            return best_class, best_id
    else:
        # Didn't beat margin
        state.candidate_class_id = None
        state.candidate_class = None
        state.candidate_frames = 0
        
    return current_stab_name, state.stabilized_class_id


class ByteTracker:
    """
    Enhanced ByteTrack Multi-Object Tracker with:
    - Smart geometric duplicate suppression (pre-tracker filtering)
    - Temporal class stabilization (post-tracker smoothing)
    - Diagnostic metrics and quality tracking
    """

    def __init__(
        self,
        model,
        tracker_config: str | None = None,
        device: str = "cpu",
        same_class_iou: float = VEHICLE_SAME_CLASS_IOU,
        cross_class_iou: float = VEHICLE_CROSS_CLASS_IOU,
        cross_class_iomin: float = VEHICLE_CROSS_CLASS_IOMIN,
        class_history_size: int = VEHICLE_CLASS_HISTORY_SIZE,
        class_switch_min_frames: int = 5,
        class_switch_conf_margin: float = 1.0,
    ) -> None:
        self._model = model
        self._tracker_config = tracker_config or "bytetrack.yaml"
        self._device = device
        self.class_history_size = class_history_size
        self.class_switch_min_frames = class_switch_min_frames
        self.class_switch_conf_margin = class_switch_conf_margin

        # Smart duplicate suppressor
        self._suppressor = VehicleDuplicateSuppressor(
            same_class_iou=same_class_iou,
            cross_class_iou=cross_class_iou,
            cross_class_iomin=cross_class_iomin,
        )

        # Internal ByteTrack instance
        # Note: frame_rate kwarg was removed in ultralytics >= 8.4; do not pass it.
        self._byte_tracker = BYTETracker(TrackerArgs())

        # Track state history: track_id → TrackState
        self._tracks: dict[int, TrackState] = {}

        # Tracking quality & diagnostic metrics
        self._id_switches: int = 0
        self._total_tracks_created: int = 0
        self._total_raw_detections: int = 0
        self._total_filtered_detections: int = 0
        self._total_same_class_suppressed: int = 0
        self._total_cross_class_suppressed: int = 0
        self._raw_class_flickers: int = 0
        self._stabilized_class_flickers: int = 0

        logger.info(
            "ByteTracker initialized with smart suppression: same_iou=%.2f, cross_iou=%.2f, history_size=%d",
            same_class_iou,
            cross_class_iou,
            class_history_size,
        )

    def update(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: float,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        iou_threshold: float = IOU_THRESHOLD,
        imgsz: int = INFERENCE_IMGSZ,
        class_filter: list[int] | None = None,
    ) -> tuple[list[TrackResult], FrameTimer]:
        """
        Run detection, duplicate suppression, ByteTrack tracking, and class stabilization.
        """
        frame_timer = FrameTimer()
        original_h, original_w = frame.shape[:2]

        # -------------------------------------------------------------------------
        # Step 1: Run YOLO detection inference
        # -------------------------------------------------------------------------
        with timer() as t:
            try:
                results = self._model.predict(
                    source=frame,
                    imgsz=imgsz,
                    conf=confidence_threshold,
                    iou=iou_threshold,
                    classes=class_filter,
                    device=self._device,
                    verbose=False,
                    stream=False,
                )
            except Exception as exc:
                logger.error("Detector error on frame %d: %s", frame_index, exc)
                return [], frame_timer

        frame_timer.inference_ms = t[0]

        # -------------------------------------------------------------------------
        # Step 2: Smart Geometric Duplicate Suppression
        # -------------------------------------------------------------------------
        raw_boxes_obj = results[0].boxes if (results and results[0].boxes is not None) else None
        num_raw = len(raw_boxes_obj) if raw_boxes_obj is not None else 0
        self._total_raw_detections += num_raw

        keep_indices: list[int] = []
        if num_raw > 0:
            boxes_np = raw_boxes_obj.xyxy.cpu().numpy()
            clses_np = raw_boxes_obj.cls.cpu().numpy()
            confs_np = raw_boxes_obj.conf.cpu().numpy()

            keep_indices, diag = self._suppressor.filter_indices(
                boxes=boxes_np,
                classes=clses_np,
                confidences=confs_np,
                class_names=self._model.names,
            )
            self._total_same_class_suppressed += diag.same_class_suppressed
            self._total_cross_class_suppressed += diag.cross_class_suppressed
            self._total_filtered_detections += len(keep_indices)
        else:
            self._total_filtered_detections += 0

        # -------------------------------------------------------------------------
        # Step 3: Pass Filtered Detections to ByteTrack
        # -------------------------------------------------------------------------
        with timer() as t:
            if num_raw > 0 and len(keep_indices) > 0:
                filtered_boxes_obj = raw_boxes_obj[
                    torch.tensor(keep_indices, device=raw_boxes_obj.xyxy.device)
                ].cpu()
                track_outputs = self._byte_tracker.update(filtered_boxes_obj)
            else:
                # Pass empty boxes on CPU
                empty_boxes = Boxes(
                    torch.zeros((0, 6)),
                    (original_h, original_w),
                )
                track_outputs = self._byte_tracker.update(empty_boxes)

        frame_timer.tracking_ms = t[0]

        # -------------------------------------------------------------------------
        # Step 4: Parse Tracks & Apply Temporal Class Stabilization
        # -------------------------------------------------------------------------
        with timer() as t:
            track_results: list[TrackResult] = []

            if track_outputs is not None and len(track_outputs) > 0:
                for row in track_outputs:
                    try:
                        x1 = max(0.0, min(float(row[0]), original_w))
                        y1 = max(0.0, min(float(row[1]), original_h))
                        x2 = max(0.0, min(float(row[2]), original_w))
                        y2 = max(0.0, min(float(row[3]), original_h))

                        if x2 <= x1 or y2 <= y1:
                            continue

                        track_id = int(row[4])
                        conf = float(row[5])
                        raw_cls_id = int(row[6])
                        raw_cls_name = to_canonical_class(self._model.names.get(raw_cls_id, f"class_{raw_cls_id}"))

                        if track_id not in self._tracks:
                            self._total_tracks_created += 1
                            state = TrackState(
                                track_id=track_id,
                                raw_class_id=raw_cls_id,
                                raw_class=raw_cls_name,
                                stabilized_class_id=raw_cls_id,
                                stabilized_class=raw_cls_name,
                                first_seen_frame=frame_index,
                                first_seen_timestamp=timestamp,
                                last_seen_frame=frame_index,
                                last_seen_timestamp=timestamp,
                                frames_seen=1,
                                last_bbox=[x1, y1, x2, y2],
                                last_confidence=conf,
                                class_history=[(raw_cls_name, raw_cls_id, conf)],
                            )
                            self._tracks[track_id] = state
                        else:
                            state = self._tracks[track_id]
                            # Track raw flicker
                            if state.raw_class_id != raw_cls_id:
                                self._raw_class_flickers += 1

                            state.raw_class_id = raw_cls_id
                            state.raw_class = raw_cls_name
                            state.last_seen_frame = frame_index
                            state.last_seen_timestamp = timestamp
                            state.frames_seen += 1
                            state.last_bbox = [x1, y1, x2, y2]
                            state.last_confidence = conf

                            # Update rolling class history
                            state.class_history.append((raw_cls_name, raw_cls_id, conf))
                            if len(state.class_history) > self.class_history_size:
                                state.class_history.pop(0)

                            # Calculate stabilized class
                            prev_stab_id = state.stabilized_class_id
                            stab_name, stab_id = stabilize_class(
                                state, 
                                min_frames=self.class_switch_min_frames, 
                                conf_margin=self.class_switch_conf_margin
                            )
                            state.stabilized_class = stab_name
                            state.stabilized_class_id = stab_id

                            if prev_stab_id != stab_id:
                                self._stabilized_class_flickers += 1
                                self._id_switches += 1

                        track_age = frame_index - state.first_seen_frame + 1
                        history_names = [item[0] for item in state.class_history]

                        track_results.append(
                            TrackResult(
                                track_id=track_id,
                                class_id=state.stabilized_class_id,
                                class_name=state.stabilized_class,
                                confidence=round(conf, 4),
                                bbox=[x1, y1, x2, y2],
                                first_seen_timestamp=state.first_seen_timestamp,
                                last_seen_timestamp=timestamp,
                                frames_seen=state.frames_seen,
                                raw_class=state.raw_class,
                                stabilized_class=state.stabilized_class,
                                class_history=history_names,
                                track_age=track_age,
                                detection_count=state.frames_seen,
                            )
                        )

                    except Exception as exc:
                        logger.warning(
                            "Failed to parse track in frame %d: %s",
                            frame_index,
                            exc,
                        )
                        continue

        frame_timer.serialization_ms = t[0]
        return track_results, frame_timer

    def get_quality_metrics(self) -> dict[str, Any]:
        """Return tracking quality & precision metrics."""
        return {
            "total_tracks_created": self._total_tracks_created,
            "active_tracks": len(self._tracks),
            "id_switches": self._id_switches,
            "total_raw_detections": self._total_raw_detections,
            "total_filtered_detections": self._total_filtered_detections,
            "total_same_class_suppressed": self._total_same_class_suppressed,
            "total_cross_class_suppressed": self._total_cross_class_suppressed,
            "raw_class_flickers": self._raw_class_flickers,
            "stabilized_class_flickers": self._stabilized_class_flickers,
        }

    def reset(self) -> None:
        """Reset tracker state. Call between videos."""
        self._tracks.clear()
        self._id_switches = 0
        self._total_tracks_created = 0
        self._total_raw_detections = 0
        self._total_filtered_detections = 0
        self._total_same_class_suppressed = 0
        self._total_cross_class_suppressed = 0
        self._raw_class_flickers = 0
        self._stabilized_class_flickers = 0
        # Reinitialize internal byte tracker
        self._byte_tracker = BYTETracker(TrackerArgs())
        logger.info("Tracker state reset")
