"""
Urban Watch — Phase 5L: Helmet Detector

Detects helmet and no-helmet events from video frames.

Model: best_roadx.pt (YOLOv8-based)
Classes: helmet, licenseplate, motorcyclist, nohelmet

CRITICAL RULES:
1. Do NOT remove helmet detection.
2. If best_roadx.pt is absent → log WARNING and disable gracefully.
3. Do NOT substitute another model without Phase benchmarking evidence.
4. licenseplate → disabled from user-facing output.
5. motorcyclist → internal tracking only.
6. helmet → user-facing HELMET event.
7. nohelmet → user-facing NO_HELMET event.
8. Temporal confirmation: require HELMET_MIN_CONFIRMATION_FRAMES detections.

Architecture:
- HelmetDetector is independent from PotholeDetector and ByteTracker.
- Runs as an additive pipeline step in UnifiedVideoProcessor.
- If model is absent, the pipeline continues normally with an empty result.

Python 3.9 compatible.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ai.common.timing import FrameTimer, timer
from ai.helmet.config import (
    HELMET_CLASS_MAPPING,
    HELMET_CLASS_NAMES,
    HELMET_CONFIDENCE_THRESHOLD,
    HELMET_FRAME_GAP_TOLERANCE,
    HELMET_IMGSZ,
    HELMET_IOU_THRESHOLD,
    HELMET_MIN_CONFIRMATION_FRAMES,
    HELMET_MODEL_PATH,
    HELMET_SUPPRESSED_CLASSES,
    HELMET_INTERNAL_CLASSES,
    HELMET_USER_FACING_CLASSES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detection result schema
# ---------------------------------------------------------------------------

@dataclass
class HelmetDetection:
    """A single helmet-related detection in a single frame."""
    class_id: int
    class_name: str                    # Raw model class name
    mapped_class: str                  # Application class name (helmet / no_helmet)
    confidence: float
    bbox: List[float]                  # [x1, y1, x2, y2] in original pixel coords
    frame_index: int
    timestamp: float
    is_user_facing: bool = True        # False for licenseplate, motorcyclist


@dataclass
class HelmetEvent:
    """A temporally confirmed helmet/no-helmet safety event."""
    event_id: int
    class_name: str                    # helmet / no_helmet
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    total_detections: int
    max_confidence: float
    mean_confidence: float
    representative_bbox: List[float]
    is_confirmed: bool = False         # True if >= HELMET_MIN_CONFIRMATION_FRAMES
    suppression_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Temporal tracker for helmet events
# ---------------------------------------------------------------------------

class HelmetEventTracker:
    """
    Minimal temporal tracker for helmet events.

    Groups frame-level detections into confirmed events.
    Similar design to PotholeEventTracker but simpler (no IoU tracking needed
    for fast-moving motorcyclists).
    """

    def __init__(
        self,
        min_confirmation_frames: int = HELMET_MIN_CONFIRMATION_FRAMES,
        frame_gap_tolerance: int = HELMET_FRAME_GAP_TOLERANCE,
    ) -> None:
        self.min_confirmation_frames = min_confirmation_frames
        self.frame_gap_tolerance = frame_gap_tolerance
        self._active: Dict[str, List[HelmetDetection]] = {}  # class → detections
        self._last_frame_by_class: Dict[str, int] = {}
        self._next_id: int = 1
        self._events: List[HelmetEvent] = []

    def update(
        self, frame_index: int, detections: List[HelmetDetection]
    ) -> None:
        """Add frame detections to running events."""
        seen_classes = set()
        for det in detections:
            if not det.is_user_facing:
                continue
            cls = det.mapped_class
            seen_classes.add(cls)

            # Start new event or extend existing
            last = self._last_frame_by_class.get(cls, -9999)
            if frame_index - last > self.frame_gap_tolerance:
                # New event
                self._active[cls] = [det]
            else:
                self._active[cls].append(det)
            self._last_frame_by_class[cls] = frame_index

    def finalize(self) -> List[HelmetEvent]:
        """Convert all accumulated detections to confirmed/unconfirmed events."""
        events = []
        for cls, dets in self._active.items():
            if not dets:
                continue
            confs = [d.confidence for d in dets]
            event = HelmetEvent(
                event_id=self._next_id,
                class_name=cls,
                first_seen_frame=dets[0].frame_index,
                first_seen_timestamp=dets[0].timestamp,
                last_seen_frame=dets[-1].frame_index,
                last_seen_timestamp=dets[-1].timestamp,
                total_detections=len(dets),
                max_confidence=max(confs),
                mean_confidence=sum(confs) / len(confs),
                representative_bbox=dets[len(dets) // 2].bbox,
                is_confirmed=len(dets) >= self.min_confirmation_frames,
            )
            self._next_id += 1
            events.append(event)
        self._events.extend(events)
        return self._events


# ---------------------------------------------------------------------------
# Helmet Detector
# ---------------------------------------------------------------------------

@dataclass
class HelmetDetectorConfig:
    model_path: str = HELMET_MODEL_PATH
    imgsz: int = HELMET_IMGSZ
    confidence_threshold: float = HELMET_CONFIDENCE_THRESHOLD
    iou_threshold: float = HELMET_IOU_THRESHOLD
    device: Optional[str] = None


class HelmetDetector:
    """
    Helmet and no-helmet safety event detector.

    Gracefully disabled if model file is not found.
    Use is_available() to check before calling detect().
    """

    def __init__(self, config: Optional[HelmetDetectorConfig] = None) -> None:
        self.config = config or HelmetDetectorConfig()
        self._model = None
        self._model_names: dict = {}
        self._is_loaded = False
        self._is_available = False
        self._unavailable_reason: Optional[str] = None

        # Check model availability at init
        if not os.path.exists(self.config.model_path):
            msg = (
                f"HelmetDetector: Model file not found: {self.config.model_path}. "
                "Helmet detection is DISABLED. "
                "Provide best_roadx.pt to enable helmet/no-helmet detection."
            )
            logger.warning(msg)
            self._unavailable_reason = f"Model not found: {self.config.model_path}"
        else:
            self._is_available = True

        self._tracker = HelmetEventTracker()

    def is_available(self) -> bool:
        """Return True if the helmet model is present and ready."""
        return self._is_available

    def load(self) -> bool:
        """
        Load the model. Returns True on success, False if unavailable.
        Silently returns False if model is absent — does not raise.
        """
        if not self._is_available:
            return False

        try:
            from ultralytics import YOLO
            from ai.common.device import get_device_info

            if self.config.device is None:
                self.config.device = get_device_info().device_str

            logger.info(
                "Loading HelmetDetector: %s (imgsz=%d, conf=%.2f, device=%s)",
                self.config.model_path,
                self.config.imgsz,
                self.config.confidence_threshold,
                self.config.device,
            )
            self._model = YOLO(self.config.model_path)
            self._model.to(self.config.device)
            self._model_names = self._model.names

            # Validate expected classes
            detected_names = set(self._model_names.values())
            missing = HELMET_CLASS_NAMES - detected_names
            if missing:
                logger.warning(
                    "HelmetDetector: missing expected classes: %s. "
                    "Model may be a different version.",
                    missing
                )

            self._is_loaded = True
            logger.info("HelmetDetector loaded successfully.")
            return True

        except Exception as exc:
            logger.error("HelmetDetector failed to load: %s", exc)
            self._is_available = False
            self._unavailable_reason = str(exc)
            return False

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> Tuple[List[HelmetDetection], Optional[FrameTimer]]:
        """
        Run helmet detection on a single frame.

        Returns (detections, timing).
        Returns ([], None) if model is unavailable.
        """
        if not self._is_available:
            return [], None

        if not self._is_loaded:
            loaded = self.load()
            if not loaded:
                return [], None

        frame_timer = FrameTimer()
        orig_h, orig_w = frame.shape[:2]

        try:
            with timer() as t:
                results = self._model.predict(
                    source=frame,
                    imgsz=self.config.imgsz,
                    conf=self.config.confidence_threshold,
                    device=self.config.device,
                    verbose=False,
                    stream=False,
                )
            frame_timer.inference_ms = t[0]

            detections = self._parse_results(results, orig_w, orig_h, frame_index, timestamp)
            self._tracker.update(frame_index, detections)
            return detections, frame_timer

        except Exception as exc:
            logger.warning("HelmetDetector error on frame %d: %s", frame_index, exc)
            return [], None

    def finalize(self) -> List[HelmetEvent]:
        """Finalize and return all confirmed helmet events."""
        return self._tracker.finalize()

    def _parse_results(
        self,
        results,
        orig_w: int,
        orig_h: int,
        frame_index: int,
        timestamp: float,
    ) -> List[HelmetDetection]:
        """Parse Ultralytics results into HelmetDetection list."""
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return []

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes
            for i in range(len(boxes)):
                try:
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = (
                        float(xyxy[0]), float(xyxy[1]),
                        float(xyxy[2]), float(xyxy[3]),
                    )
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())
                    raw_name = self._model_names.get(cls_id, f"class_{cls_id}")

                    # Clip to frame
                    x1 = max(0.0, min(x1, orig_w))
                    y1 = max(0.0, min(y1, orig_h))
                    x2 = max(0.0, min(x2, orig_w))
                    y2 = max(0.0, min(y2, orig_h))

                    if x2 <= x1 or y2 <= y1:
                        continue

                    mapped = HELMET_CLASS_MAPPING.get(raw_name, raw_name)
                    is_user_facing = raw_name in HELMET_USER_FACING_CLASSES

                    detections.append(HelmetDetection(
                        class_id=cls_id,
                        class_name=raw_name,
                        mapped_class=mapped,
                        confidence=round(conf, 4),
                        bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                        frame_index=frame_index,
                        timestamp=timestamp,
                        is_user_facing=is_user_facing,
                    ))

                except Exception as exc:
                    logger.debug("HelmetDetector parse error at index %d: %s", i, exc)
                    continue

        return detections

    def reset(self) -> None:
        """Reset tracker state between videos."""
        self._tracker = HelmetEventTracker()
        # Keep model loaded across videos
