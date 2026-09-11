"""
Urban Watch — Waterlogging Detector
Runs segmentation inference to detect road waterlogging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from ultralytics import YOLO

from ai.common.device import get_device_info
from ai.common.timing import FrameTimer, timer
from ai.waterlogging.config import (
    DEFAULT_WATERLOGGING_MODEL,
    WATERLOGGING_CONFIDENCE_THRESHOLD,
    WATERLOGGING_IMGSZ,
    WATERLOGGING_IOU_THRESHOLD,
)
from ai.waterlogging.schemas import WaterloggingDetection

logger = logging.getLogger(__name__)


@dataclass
class WaterloggingDetectorConfig:
    model_path: str = DEFAULT_WATERLOGGING_MODEL
    imgsz: int = WATERLOGGING_IMGSZ
    confidence_threshold: float = WATERLOGGING_CONFIDENCE_THRESHOLD
    iou_threshold: float = WATERLOGGING_IOU_THRESHOLD
    device: Optional[str] = None


class ModelNotFoundError(Exception):
    def __init__(self, message: str, resolved_path: str):
        super().__init__(message)
        self.resolved_path = resolved_path

class WaterloggingDetector:
    """Production Waterlogging Detector Engine using Segmentation."""

    def __init__(self, config: Optional[WaterloggingDetectorConfig] = None) -> None:
        self.config = config or WaterloggingDetectorConfig()
        if self.config.device is None:
            self.config.device = get_device_info().device_str

        self._model = None
        self._is_loaded = False

    def load(self) -> None:
        """Load the segmentation model."""
        import os
        from pathlib import Path
        
        resolved_path = Path(self.config.model_path).resolve()
        
        if not resolved_path.exists():
            error_msg = f"Waterlogging model not found:\n{resolved_path}"
            logger.error(error_msg)
            raise ModelNotFoundError(error_msg, str(resolved_path))
            
        logger.info(
            "Loading WaterloggingDetector: %s (imgsz=%d, conf=%.2f, device=%s)",
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
    ) -> Tuple[List[WaterloggingDetection], FrameTimer]:
        if not self._is_loaded or self._model is None:
            self.load()

        frame_timer = FrameTimer()
        orig_h, orig_w = frame.shape[:2]

        with timer() as t:
            # We enforce task="segment" if using a segmentation model.
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
    ) -> List[WaterloggingDetection]:
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return []

        boxes_obj = results[0].boxes
        xyxy = boxes_obj.xyxy.cpu().numpy()
        confs = boxes_obj.conf.cpu().numpy()
        
        # Check if masks exist
        has_masks = results[0].masks is not None
        if has_masks:
            # xyn gives normalized coordinates, xy gives pixel coordinates
            # shape: (N, num_points, 2) where N is number of detections
            masks_xy = results[0].masks.xy

        # Apply simple NMS just in case if the model hasn't suppressed heavily overlapped instances
        keep_indices = self._deduplicate_boxes(xyxy, confs, self.config.iou_threshold)

        detections: List[WaterloggingDetection] = []
        for idx in keep_indices:
            box = xyxy[idx]
            conf = float(confs[idx])

            x1 = max(0.0, min(float(box[0]), float(orig_w)))
            y1 = max(0.0, min(float(box[1]), float(orig_h)))
            x2 = max(0.0, min(float(box[2]), float(orig_w)))
            y2 = max(0.0, min(float(box[3]), float(orig_h)))

            if x2 <= x1 or y2 <= y1:
                continue

            polygon = []
            area_ratio = 0.0
            
            if has_masks and idx < len(masks_xy):
                poly = masks_xy[idx]
                if len(poly) > 2:
                    polygon = [
                        [
                            max(0.0, min(round(float(pt[0]), 1), float(orig_w))),
                            max(0.0, min(round(float(pt[1]), 1), float(orig_h)))
                        ] 
                        for pt in poly
                    ]
                    
                    # Compute Shoelace area
                    area = 0.0
                    n = len(poly)
                    for i in range(n):
                        j = (i + 1) % n
                        area += poly[i][0] * poly[j][1]
                        area -= poly[j][0] * poly[i][1]
                    area = abs(area) / 2.0
                    
                    bbox_area = (x2 - x1) * (y2 - y1)
                    if bbox_area > 0:
                        area_ratio = min(1.0, area / bbox_area)

            detections.append(
                WaterloggingDetection(
                    class_id=0,
                    class_name="waterlogging",
                    confidence=round(conf, 4),
                    bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                    polygon=polygon,
                    area_ratio=round(area_ratio, 3)
                )
            )

        return detections

    def _deduplicate_boxes(self, boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
        if len(boxes) == 0:
            return []
        
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            
            # Use areas[i] instead of combined union if we want strict overlapping suppression
            # We'll use standard IoU
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep
