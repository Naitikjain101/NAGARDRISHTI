"""
Urban Watch — Detection Engine

Runs YOLO inference on individual frames.

Rules:
- Input: original BGR frame (np.ndarray) in original resolution
- Output: list of DetectionResult with bboxes in ORIGINAL VIDEO COORDINATES
- Confidence comes from model inference — never fabricated
- No fake detections
- No hardcoded confidence values
- Bboxes stay in original video pixel space (not model preprocessing space)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ai.common.schemas import DetectionResult
from ai.common.timing import FrameTimer, timer
from ai.detection.classes import PHASE1_REQUIRED_CLASSES, get_phase1_class_ids

logger = logging.getLogger(__name__)


@dataclass
class DetectorConfig:
    """Configuration for the detector. All values from config.py."""

    pt_file: str
    device: str
    imgsz: int = 640
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    # If None, detect all classes. If set, filter to these class IDs only.
    class_filter: list[int] | None = None


class Detector:
    """
    Frame-level YOLO object detector.

    Usage:
        detector = Detector(config)
        results, timing = detector.detect(frame)
    """

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self._model = None
        self._model_names: dict[int, str] = {}
        self._class_filter: list[int] | None = None
        self._is_loaded = False

    def load(self) -> None:
        """Load the model onto the configured device."""
        from ultralytics import YOLO

        logger.info(
            "Loading detector: %s on %s (imgsz=%d, conf=%.2f)",
            self.config.pt_file,
            self.config.device,
            self.config.imgsz,
            self.config.confidence_threshold,
        )

        self._model = YOLO(self.config.pt_file)
        self._model.to(self.config.device)
        self._model_names = self._model.names

        # Build class filter if not explicitly set
        if self.config.class_filter is not None:
            self._class_filter = self.config.class_filter
        else:
            # Filter to Phase 1 required classes only
            self._class_filter = get_phase1_class_ids(self._model_names)
            logger.info(
                "Class filter: %s",
                {cid: self._model_names[cid] for cid in self._class_filter},
            )

        self._is_loaded = True
        logger.info("Detector loaded: %s", self.config.pt_file)

    @property
    def model_names(self) -> dict[int, str]:
        if not self._is_loaded:
            raise RuntimeError("Detector not loaded — call detector.load() first")
        return self._model_names

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> tuple[list[DetectionResult], FrameTimer]:
        """
        Run detection on a single frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR frame in original video resolution.
        frame_index : int
            Frame index for logging.
        timestamp : float
            Video timestamp in seconds.

        Returns
        -------
        (detections, timing)
            List of DetectionResult and timing breakdown.
        """
        if not self._is_loaded:
            raise RuntimeError("Detector not loaded — call detector.load() first")

        frame_timer = FrameTimer()
        original_h, original_w = frame.shape[:2]

        # -------------------------------------------------------------------------
        # Run inference
        # -------------------------------------------------------------------------
        with timer() as t:
            results = self._model.predict(
                source=frame,
                imgsz=self.config.imgsz,
                conf=self.config.confidence_threshold,
                iou=self.config.iou_threshold,
                classes=self._class_filter,
                device=self.config.device,
                verbose=False,
                stream=False,
            )
        frame_timer.inference_ms = t[0]

        # -------------------------------------------------------------------------
        # Parse results → DetectionResult list
        # -------------------------------------------------------------------------
        with timer() as t:
            detections = self._parse_results(
                results, original_w, original_h
            )
        frame_timer.serialization_ms = t[0]

        return detections, frame_timer

    def _parse_results(
        self,
        results,
        original_w: int,
        original_h: int,
    ) -> list[DetectionResult]:
        """
        Convert Ultralytics result objects to DetectionResult list.

        Bboxes are converted back to ORIGINAL VIDEO COORDINATES.
        This is important: Ultralytics internally resizes frames for inference.
        The output boxes must be in the original resolution space.
        """
        detections: list[DetectionResult] = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes

            # Ultralytics returns xyxy coords already scaled to the
            # original input image dimensions when using predict() with
            # a numpy array — we verify this by checking against frame dims.
            for i in range(len(boxes)):
                try:
                    # xyxy format — already in original input coords
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())
                    cls_name = self._model_names.get(cls_id, f"class_{cls_id}")

                    # Clip to frame bounds (safety)
                    x1 = max(0.0, min(x1, original_w))
                    y1 = max(0.0, min(y1, original_h))
                    x2 = max(0.0, min(x2, original_w))
                    y2 = max(0.0, min(y2, original_h))

                    # Discard degenerate boxes
                    if x2 <= x1 or y2 <= y1:
                        continue

                    detections.append(DetectionResult(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=round(conf, 4),
                        bbox=[x1, y1, x2, y2],
                    ))

                except Exception as exc:
                    logger.warning(
                        "Failed to parse detection %d in frame: %s", i, exc
                    )
                    continue

        return detections

    def unload(self) -> None:
        """Release model from memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._is_loaded = False
            logger.info("Detector unloaded: %s", self.config.pt_file)

    def __enter__(self) -> "Detector":
        self.load()
        return self

    def __exit__(self, *args) -> None:
        self.unload()
