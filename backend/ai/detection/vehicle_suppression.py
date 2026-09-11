"""
Urban Watch — Smart Geometric Vehicle Duplicate Suppression

Filters duplicate and cross-class phantom bounding boxes before tracking.

Rules:
1. Same-class duplicates:
   - IoU >= same_class_iou (default 0.75) -> retain higher-confidence detection.
2. Confusable cross-class pairs (car/truck, bus/truck, motorcycle/bicycle):
   - Suppress when:
     (IoU >= cross_class_iou (default 0.65))
     OR
     (IoMin >= cross_class_iomin (default 0.80) AND smaller box center is inside larger box)
   - Retain higher-confidence detection.
3. Protected pairs:
   - Never suppress person + motorcycle or person + bicycle.
   - Never suppress legitimate adjacent vehicles unless strict geometric criteria are met.
4. All thresholds are configurable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

import numpy as np

from ai.common.config import (
    CONFUSABLE_CROSS_CLASS_PAIRS,
    VEHICLE_CROSS_CLASS_IOMIN,
    VEHICLE_CROSS_CLASS_IOU,
    VEHICLE_SAME_CLASS_IOU,
)
from ai.common.schemas import DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class SuppressionDiagnostics:
    """Diagnostic metrics for a single frame or run."""

    raw_detections: int = 0
    filtered_detections: int = 0
    same_class_suppressed: int = 0
    cross_class_suppressed: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)


class VehicleDuplicateSuppressor:
    """
    Reusable vehicle post-processing duplicate suppression engine.
    """

    def __init__(
        self,
        same_class_iou: float = VEHICLE_SAME_CLASS_IOU,
        cross_class_iou: float = VEHICLE_CROSS_CLASS_IOU,
        cross_class_iomin: float = VEHICLE_CROSS_CLASS_IOMIN,
        confusable_pairs: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.same_class_iou = same_class_iou
        self.cross_class_iou = cross_class_iou
        self.cross_class_iomin = cross_class_iomin
        
        pairs = confusable_pairs or CONFUSABLE_CROSS_CLASS_PAIRS
        # Normalize pairs as sets of lowercase strings for fast bidirectional matching
        self._confusable_sets: list[set[str]] = [
            {p[0].lower(), p[1].lower()} for p in pairs
        ]

    def _is_confusable(self, class1: str, class2: str) -> bool:
        """Check if class1 and class2 form a known confusable vehicle pair."""
        c_set = {class1.lower(), class2.lower()}
        return any(c_set == s for s in self._confusable_sets)

    def compute_geometry(
        self, b1: List[float] | np.ndarray, b2: List[float] | np.ndarray
    ) -> dict[str, Any]:
        """
        Compute IoU, IoMin (intersection / min_area), and containment.
        b1, b2 are [x1, y1, x2, y2].
        """
        x1 = max(float(b1[0]), float(b2[0]))
        y1 = max(float(b1[1]), float(b2[1]))
        x2 = min(float(b1[2]), float(b2[2]))
        y2 = min(float(b1[3]), float(b2[3]))

        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter_area = inter_w * inter_h

        area1 = max(0.0, float(b1[2] - b1[0]) * float(b1[3] - b1[1]))
        area2 = max(0.0, float(b2[2] - b2[0]) * float(b2[3] - b2[1]))

        union_area = area1 + area2 - inter_area
        iou = (inter_area / union_area) if union_area > 0.0 else 0.0

        min_area = min(area1, area2)
        iomin = (inter_area / min_area) if min_area > 0.0 else 0.0

        # Center containment
        c1 = ((b1[0] + b1[2]) / 2.0, (b1[1] + b1[3]) / 2.0)
        c2 = ((b2[0] + b2[2]) / 2.0, (b2[1] + b2[3]) / 2.0)

        if area1 <= area2:
            smaller_center_in_larger = (
                b2[0] <= c1[0] <= b2[2] and b2[1] <= c1[1] <= b2[3]
            )
        else:
            smaller_center_in_larger = (
                b1[0] <= c2[0] <= b1[2] and b1[1] <= c2[1] <= b1[3]
            )

        return {
            "iou": iou,
            "iomin": iomin,
            "area1": area1,
            "area2": area2,
            "smaller_center_in_larger": smaller_center_in_larger,
        }

    def should_suppress(
        self,
        cls_high: str,
        box_high: List[float] | np.ndarray,
        cls_low: str,
        box_low: List[float] | np.ndarray,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if the lower-confidence detection should be suppressed
        by the higher-confidence detection.

        Returns:
            (should_suppress: bool, reason: Optional[str])
        """
        # Protected relationships: Never suppress person vs vehicle
        cls_high_lower = cls_high.lower()
        cls_low_lower = cls_low.lower()
        if "person" in (cls_high_lower, cls_low_lower):
            return False, None

        geom = self.compute_geometry(box_high, box_low)
        iou = geom["iou"]
        iomin = geom["iomin"]
        center_in_larger = geom["smaller_center_in_larger"]

        # Case 1: Same class duplicates
        if cls_high_lower == cls_low_lower:
            if iou >= self.same_class_iou:
                return True, f"same-class duplicate (IoU={iou:.3f} >= {self.same_class_iou})"
            return False, None

        # Case 2: Confusable cross-class vehicle pairs
        if self._is_confusable(cls_high_lower, cls_low_lower):
            if iou >= self.cross_class_iou:
                return (
                    True,
                    f"cross-class confusable pair ({cls_high}/{cls_low}) IoU={iou:.3f} >= {self.cross_class_iou}",
                )
            if iomin >= self.cross_class_iomin and center_in_larger:
                return (
                    True,
                    f"cross-class confusable nested ({cls_high}/{cls_low}) IoMin={iomin:.3f} >= {self.cross_class_iomin} with center containment",
                )

        return False, None

    def filter_indices(
        self,
        boxes: np.ndarray | list,
        classes: np.ndarray | list,
        confidences: np.ndarray | list,
        class_names: dict[int, str] | list[str],
    ) -> tuple[list[int], SuppressionDiagnostics]:
        """
        Filter candidate detections by array representation.

        Parameters
        ----------
        boxes : array of [x1, y1, x2, y2]
        classes : array of class_ids
        confidences : array of floats
        class_names : mapping of class_id -> class_name

        Returns
        -------
        (keep_indices: list[int], diagnostics: SuppressionDiagnostics)
        """
        num_boxes = len(boxes)
        diag = SuppressionDiagnostics(raw_detections=num_boxes)

        if num_boxes == 0:
            diag.filtered_detections = 0
            return [], diag

        if num_boxes == 1:
            diag.filtered_detections = 1
            return [0], diag

        # Get class names
        def get_name(cid: int) -> str:
            if isinstance(class_names, dict):
                return class_names.get(int(cid), f"class_{cid}")
            return str(class_names[int(cid)])

        c_names = [get_name(int(c)) for c in classes]

        # Sort indices by confidence descending
        sorted_indices = sorted(
            range(num_boxes), key=lambda idx: float(confidences[idx]), reverse=True
        )

        suppressed_indices: set[int] = set()

        for si in range(len(sorted_indices)):
            idx_high = sorted_indices[si]
            if idx_high in suppressed_indices:
                continue

            cls_high = c_names[idx_high]
            box_high = boxes[idx_high]

            for sj in range(si + 1, len(sorted_indices)):
                idx_low = sorted_indices[sj]
                if idx_low in suppressed_indices:
                    continue

                cls_low = c_names[idx_low]
                box_low = boxes[idx_low]

                suppress, reason = self.should_suppress(
                    cls_high, box_high, cls_low, box_low
                )

                if suppress:
                    suppressed_indices.add(idx_low)
                    if cls_high.lower() == cls_low.lower():
                        diag.same_class_suppressed += 1
                    else:
                        diag.cross_class_suppressed += 1

                    diag.events.append(
                        {
                            "suppressed_idx": idx_low,
                            "retained_idx": idx_high,
                            "suppressed_class": cls_low,
                            "retained_class": cls_high,
                            "reason": reason,
                        }
                    )

        keep_indices = [
            i for i in range(num_boxes) if i not in suppressed_indices
        ]
        diag.filtered_detections = len(keep_indices)
        return keep_indices, diag

    def suppress_detections(
        self, detections: list[DetectionResult]
    ) -> tuple[list[DetectionResult], SuppressionDiagnostics]:
        """
        Filter a list of DetectionResult objects.
        """
        if not detections:
            return [], SuppressionDiagnostics()

        boxes = [d.bbox for d in detections]
        classes = [d.class_id for d in detections]
        confidences = [d.confidence for d in detections]
        class_names = {d.class_id: d.class_name for d in detections}

        keep_indices, diag = self.filter_indices(
            boxes, classes, confidences, class_names
        )

        filtered = [detections[i] for i in keep_indices]
        return filtered, diag
