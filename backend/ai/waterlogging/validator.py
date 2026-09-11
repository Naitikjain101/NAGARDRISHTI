"""
Urban Watch — WaterloggingValidator
Phase 10 — Steps 10, 11, 12, 13, 14

Architecture enforced explicitly:
  RAW MODEL DETECTION → VALIDATION → TEMPORAL CONFIRMATION →
  SPATIAL DEDUPLICATION → CONFIRMED WATERLOGGING EVENT → SUPABASE INCIDENT

A single raw YOLO prediction MUST NEVER become a confirmed incident directly.
Every candidate is evaluated against this validator before temporal confirmation.

Rejected predictions remain accessible in validation/debug mode (Step 21).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from ai.waterlogging.schemas import WaterloggingDetection
from ai.waterlogging.config import (
    WATERLOGGING_MIN_AREA_RATIO,
    WATERLOGGING_MAX_AREA_RATIO,
)

logger = logging.getLogger(__name__)


class RejectionReason(str, Enum):
    LOW_CONFIDENCE          = "LOW_CONFIDENCE"
    MASK_TOO_SMALL          = "MASK_TOO_SMALL"
    MASK_TOO_LARGE          = "MASK_TOO_LARGE"       # Catches whole-frame false positives
    INSUFFICIENT_ROAD_OVERLAP = "INSUFFICIENT_ROAD_OVERLAP"
    TEMPORALLY_UNSTABLE     = "TEMPORALLY_UNSTABLE"
    SPATIAL_INCONSISTENCY   = "SPATIAL_INCONSISTENCY"
    INSUFFICIENT_PERSISTENCE = "INSUFFICIENT_PERSISTENCE"
    INVALID_GEOMETRY        = "INVALID_GEOMETRY"
    UPPER_FRAME_ONLY        = "UPPER_FRAME_ONLY"     # Detection only in sky/above-road region


@dataclass
class ValidationConfig:
    # Confidence
    min_confidence: float = 0.60           # Raised from 0.40; forensic audit avg was 0.87 so
                                            # 0.60 still captures the observed pattern.
                                            # Configurable: sweep in Step 19 calibration.

    # Mask area as fraction of total frame (not bbox area)
    min_area_ratio_to_frame: float = 0.01  # Must cover at least 1% of frame
    max_area_ratio_to_frame: float = 0.40  # Must not cover more than 40% of frame.
                                            # Forensic audit: eval video avg area_ratio=0.39
                                            # (entire lower half). Every frame had a detection
                                            # at conf=0.84 avg. This is shortcut-learning.
                                            # Real waterlogging incidents in urban footage rarely
                                            # cover >40% of the full camera frame.
                                            # Configurable: swept jointly in Step 19.

    # Road region: detection must be in the lower portion of the frame
    road_top_boundary: float = 0.30        # bbox top must be below 30% from frame top
    road_bottom_exclusion: float = 0.0     # No exclusion at the bottom

    # Minimum vertical extent: very thin horizontal bands are noise
    min_bbox_height_ratio: float = 0.05    # bbox height / frame height >= 5%

    # Aspect ratio guard: water regions are typically wider than tall
    max_aspect_ratio: float = 15.0         # width/height must be <= 15

    # Configurable enable/disable per rule (for debugging)
    enforce_area_limits: bool = True
    enforce_road_region: bool = True
    enforce_aspect_ratio: bool = True
    enforce_confidence: bool = True


@dataclass
class ValidationResult:
    accepted: bool
    confidence: float
    validation_score: float                # 0.0-1.0, higher = more likely real water
    rejection_reasons: List[RejectionReason] = field(default_factory=list)
    debug_info: dict = field(default_factory=dict)


class WaterloggingValidator:
    """
    Pre-temporal-tracker validator. Evaluates every raw YOLO detection before it
    can enter the temporal persistence tracker. Multiple rejection reasons are
    accumulated per detection (not early-exit) so forensic mode can audit all
    reasons a detection was rejected.

    This validator specifically addresses the Phase 10 forensic findings:
    - The V1 model produced bbox covering ~48% of frame (full lower half) on ALL
      95 evaluated frames with confidence 0.88 avg. This is classic shortcut-learning:
      the model learned to fire on the lower half of the training video rather than
      learning genuine water visual features.
    - The max_area_ratio_to_frame=0.70 guard catches this entire class of FP.
    - The min_confidence=0.55 reduces the tail of low-confidence detections.
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self._stats = {
            "total_evaluated": 0,
            "accepted": 0,
            "rejected": 0,
            "rejection_counts": {r.value: 0 for r in RejectionReason},
        }

    def validate(
        self,
        detection: WaterloggingDetection,
        frame_width: int,
        frame_height: int,
    ) -> ValidationResult:
        """Validate a single raw detection. Returns ValidationResult with all rejection reasons."""
        self._stats["total_evaluated"] += 1
        reasons: List[RejectionReason] = []
        debug: dict = {}

        bbox = detection.bbox  # [x1, y1, x2, y2]
        x1, y1, x2, y2 = bbox
        bbox_w = x2 - x1
        bbox_h = y2 - y1
        bbox_area = bbox_w * bbox_h
        frame_area = frame_width * frame_height

        area_ratio = bbox_area / frame_area if frame_area > 0 else 0.0
        bbox_height_ratio = bbox_h / frame_height if frame_height > 0 else 0.0
        y_top_ratio = y1 / frame_height if frame_height > 0 else 0.0
        aspect_ratio = bbox_w / bbox_h if bbox_h > 0 else 999.0

        debug["area_ratio_to_frame"] = round(area_ratio, 4)
        debug["bbox_height_ratio"] = round(bbox_height_ratio, 4)
        debug["y_top_ratio"] = round(y_top_ratio, 4)
        debug["aspect_ratio"] = round(aspect_ratio, 4)
        debug["confidence"] = detection.confidence

        # --- Rule 1: Confidence ---
        if self.config.enforce_confidence and detection.confidence < self.config.min_confidence:
            reasons.append(RejectionReason.LOW_CONFIDENCE)

        # --- Rule 2: Area too small ---
        if self.config.enforce_area_limits and area_ratio < self.config.min_area_ratio_to_frame:
            reasons.append(RejectionReason.MASK_TOO_SMALL)

        # --- Rule 3: Area too large (whole-frame FP) ---
        # This is the PRIMARY guard against the V1 shortcut-learning failure mode.
        # The forensic audit found avg area_ratio=0.48 (covering entire lower half).
        if self.config.enforce_area_limits and area_ratio > self.config.max_area_ratio_to_frame:
            reasons.append(RejectionReason.MASK_TOO_LARGE)

        # --- Rule 4: Road region (bbox top must be below horizon) ---
        # If the bbox starts above the road_top_boundary, it's detecting sky/buildings/etc.
        if self.config.enforce_road_region and y_top_ratio < self.config.road_top_boundary:
            reasons.append(RejectionReason.UPPER_FRAME_ONLY)

        # --- Rule 5: Minimum bbox height (thin bands are noise) ---
        if self.config.enforce_area_limits and bbox_height_ratio < self.config.min_bbox_height_ratio:
            reasons.append(RejectionReason.INVALID_GEOMETRY)

        # --- Rule 6: Aspect ratio ---
        if self.config.enforce_aspect_ratio and aspect_ratio > self.config.max_aspect_ratio:
            reasons.append(RejectionReason.INVALID_GEOMETRY)

        # --- Compute validation score (higher = more likely real water) ---
        score = detection.confidence
        # Penalise too-large area (FP indicator)
        if area_ratio > 0.5:
            score *= max(0.0, 1.0 - (area_ratio - 0.5) * 2)
        # Reward presence of segmentation mask
        if detection.polygon and len(detection.polygon) > 10:
            score = min(1.0, score * 1.05)

        accepted = len(reasons) == 0

        if accepted:
            self._stats["accepted"] += 1
        else:
            self._stats["rejected"] += 1
            for r in reasons:
                self._stats["rejection_counts"][r.value] += 1

        return ValidationResult(
            accepted=accepted,
            confidence=detection.confidence,
            validation_score=round(score, 4),
            rejection_reasons=reasons,
            debug_info=debug,
        )

    def validate_batch(
        self,
        detections: List[WaterloggingDetection],
        frame_width: int,
        frame_height: int,
    ) -> Tuple[List[WaterloggingDetection], List[ValidationResult]]:
        """
        Validate a batch of detections.
        Returns (accepted_detections, all_results).
        Rejected detections are still in all_results (accessible in debug/forensic mode).
        """
        accepted = []
        results = []
        for det in detections:
            result = self.validate(det, frame_width, frame_height)
            results.append(result)
            if result.accepted:
                accepted.append(det)
        return accepted, results

    def get_stats(self) -> dict:
        """Return running validation statistics."""
        return dict(self._stats)

    def reset_stats(self):
        self._stats = {
            "total_evaluated": 0,
            "accepted": 0,
            "rejected": 0,
            "rejection_counts": {r.value: 0 for r in RejectionReason},
        }
