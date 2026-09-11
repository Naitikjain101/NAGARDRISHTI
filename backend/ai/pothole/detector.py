"""
Urban Watch — Pothole Detector

Runs inference on single frames and returns detections mapped to the original image coordinate space.
Features:
- Hardware acceleration (MPS / CUDA / CPU) via Device Manager
- Intra-frame duplicate suppression (NMS)
- Exact inverse coordinate transformation from letterbox space to original dimensions
- Microsecond execution profiling
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from ultralytics import YOLO

from ai.common.device import get_device_info
from ai.common.timing import FrameTimer, timer
from ai.pothole.config import (
    DEFAULT_POTHOLE_MODEL,
    POTHOLE_CONFIDENCE_THRESHOLD,
    POTHOLE_IMGSZ,
    POTHOLE_IOU_THRESHOLD,
)
from ai.pothole.schemas import PotholeDetection

logger = logging.getLogger(__name__)


@dataclass
class PotholeDetectorConfig:
    model_path: str = DEFAULT_POTHOLE_MODEL
    imgsz: int = POTHOLE_IMGSZ
    confidence_threshold: float = POTHOLE_CONFIDENCE_THRESHOLD
    iou_threshold: float = POTHOLE_IOU_THRESHOLD
    device: Optional[str] = None


class PotholeDetector:
    """Production Pothole Detector Engine."""

    def __init__(self, config: Optional[PotholeDetectorConfig] = None) -> None:
        self.config = config or PotholeDetectorConfig()
        if self.config.device is None:
            self.config.device = get_device_info().device_str

        self._model = None
        self._is_loaded = False

    def load(self) -> None:
        """Load the model onto the configured accelerator."""
        logger.info(
            "Loading PotholeDetector: %s (imgsz=%d, conf=%.2f, device=%s)",
            self.config.model_path,
            self.config.imgsz,
            self.config.confidence_threshold,
            self.config.device,
        )
        self._model = YOLO(self.config.model_path)
        self._model.to(self.config.device)
        self._is_loaded = True

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> Tuple[List[PotholeDetection], FrameTimer]:
        """
        Run pothole detection on a single frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR image in original video/image resolution.
        frame_index : int
            Current frame index.
        timestamp : float
            Timestamp in seconds.

        Returns
        -------
        (detections, timing)
        """
        if not self._is_loaded or self._model is None:
            self.load()

        frame_timer = FrameTimer()
        orig_h, orig_w = frame.shape[:2]

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

        with timer() as t:
            detections = self._process_results(results, orig_w, orig_h)
        frame_timer.serialization_ms = t[0]

        return detections, frame_timer

    def _process_results(
        self,
        results,
        orig_w: int,
        orig_h: int,
    ) -> List[PotholeDetection]:
        """Extract boxes, perform NMS deduplication, and map to original coordinates."""
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return []

        boxes_obj = results[0].boxes
        xyxy = boxes_obj.xyxy.cpu().numpy()
        confs = boxes_obj.conf.cpu().numpy()

        # Intra-frame duplicate suppression (NMS)
        keep_indices = self._deduplicate_boxes(xyxy, confs, self.config.iou_threshold)

        detections: List[PotholeDetection] = []
        for idx in keep_indices:
            box = xyxy[idx]
            conf = float(confs[idx])

            # Ultralytics xyxy with ndarray predict is already mapped back to input frame dimensions
            x1 = max(0.0, min(float(box[0]), float(orig_w)))
            y1 = max(0.0, min(float(box[1]), float(orig_h)))
            x2 = max(0.0, min(float(box[2]), float(orig_w)))
            y2 = max(0.0, min(float(box[3]), float(orig_h)))

            if x2 <= x1 or y2 <= y1:
                continue

            detections.append(
                PotholeDetection(
                    class_id=0,
                    class_name="pothole",
                    confidence=round(conf, 4),
                    bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                )
            )

        return detections

    @staticmethod
    def _deduplicate_boxes(
        xyxy: np.ndarray,
        confs: np.ndarray,
        iou_threshold: float,
    ) -> List[int]:
        """Suppresses intra-frame duplicate detections using Non-Maximum Suppression."""
        if len(xyxy) == 0:
            return []

        order = confs.argsort()[::-1]
        keep = []

        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            if order.size == 1:
                break

            xx1 = np.maximum(xyxy[i, 0], xyxy[order[1:], 0])
            yy1 = np.maximum(xyxy[i, 1], xyxy[order[1:], 1])
            xx2 = np.minimum(xyxy[i, 2], xyxy[order[1:], 2])
            yy2 = np.minimum(xyxy[i, 3], xyxy[order[1:], 3])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h

            area_i = (xyxy[i, 2] - xyxy[i, 0]) * (xyxy[i, 3] - xyxy[i, 1])
            area_others = (xyxy[order[1:], 2] - xyxy[order[1:], 0]) * (
                xyxy[order[1:], 3] - xyxy[order[1:], 1]
            )
            union = area_i + area_others - inter
            iou = inter / (union + 1e-6)

            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep
