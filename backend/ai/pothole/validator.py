"""
Urban Watch — Phase 5C: PotholeValidator

Multi-signal composite confidence scoring for pothole events.

The raw YOLOv8m_peterhdd model still generates false positives on visually
similar road textures. This validator calculates a composite score based on
multiple evidence signals to estimate how likely an event is a real pothole.

IMPORTANT:
- This is NOT a replacement for the existing filtering pipeline.
- It runs AFTER PotholeEventTracker, as a post-event enrichment pass.
- The composite_score is advisory metadata — it enriches events but does NOT
  change the fundamental confirmed/rejected/suppressed status unless the score
  falls below POTHOLE_MIN_INCIDENT_SCORE.
- All weights are configured in ai/common/config.py — NOT hardcoded here.

Signal Description
------------------
1. model_confidence   — Average model confidence across all detections
2. temporal_persistence — Event span normalized by min required frames
3. spatial_stability  — Inverse of normalized bbox center variance
4. geometry_score     — Bbox size appropriateness relative to frame
5. detection_frequency — detection_count / span_frames (density in time)
6. vehicle_overlap    — Penalty if event was under a vehicle

All signals produce values in [0, 1].
Composite = weighted_sum(signals) - overlap_penalty
Clamped to [0, 1].
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

from ai.common.config import (
    POTHOLE_WEIGHT_MODEL_CONFIDENCE,
    POTHOLE_WEIGHT_TEMPORAL,
    POTHOLE_WEIGHT_SPATIAL,
    POTHOLE_WEIGHT_GEOMETRY,
    POTHOLE_WEIGHT_FREQUENCY,
    POTHOLE_VEHICLE_OVERLAP_PENALTY,
    POTHOLE_MIN_TEMPORAL_FRAMES,
    POTHOLE_MIN_INCIDENT_SCORE,
    POTHOLE_MIN_AREA_RATIO,
    POTHOLE_MAX_AREA_RATIO,
)

logger = logging.getLogger(__name__)


class PotholeValidatorConfig:
    """
    Configuration for PotholeValidator.
    All values sourced from ai/common/config.py for single source of truth.
    """
    def __init__(
        self,
        weight_model_confidence: float = POTHOLE_WEIGHT_MODEL_CONFIDENCE,
        weight_temporal: float = POTHOLE_WEIGHT_TEMPORAL,
        weight_spatial: float = POTHOLE_WEIGHT_SPATIAL,
        weight_geometry: float = POTHOLE_WEIGHT_GEOMETRY,
        weight_frequency: float = POTHOLE_WEIGHT_FREQUENCY,
        vehicle_overlap_penalty: float = POTHOLE_VEHICLE_OVERLAP_PENALTY,
        min_temporal_frames: int = POTHOLE_MIN_TEMPORAL_FRAMES,
        min_incident_score: float = POTHOLE_MIN_INCIDENT_SCORE,
        min_area_ratio: float = POTHOLE_MIN_AREA_RATIO,
        max_area_ratio: float = POTHOLE_MAX_AREA_RATIO,
    ) -> None:
        self.weight_model_confidence = weight_model_confidence
        self.weight_temporal = weight_temporal
        self.weight_spatial = weight_spatial
        self.weight_geometry = weight_geometry
        self.weight_frequency = weight_frequency
        self.vehicle_overlap_penalty = vehicle_overlap_penalty
        self.min_temporal_frames = min_temporal_frames
        self.min_incident_score = min_incident_score
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio


class ValidationSignals:
    """Intermediate scoring signals for a single event — for logging/debugging."""

    def __init__(
        self,
        model_confidence: float,
        temporal_score: float,
        spatial_score: float,
        geometry_score: float,
        frequency_score: float,
        has_vehicle_overlap: bool,
        composite_score: float,
        is_above_threshold: bool,
    ) -> None:
        self.model_confidence = model_confidence
        self.temporal_score = temporal_score
        self.spatial_score = spatial_score
        self.geometry_score = geometry_score
        self.frequency_score = frequency_score
        self.has_vehicle_overlap = has_vehicle_overlap
        self.composite_score = composite_score
        self.is_above_threshold = is_above_threshold

    def to_dict(self) -> dict:
        return {
            "model_confidence": round(self.model_confidence, 4),
            "temporal_score": round(self.temporal_score, 4),
            "spatial_score": round(self.spatial_score, 4),
            "geometry_score": round(self.geometry_score, 4),
            "frequency_score": round(self.frequency_score, 4),
            "has_vehicle_overlap": self.has_vehicle_overlap,
            "composite_score": round(self.composite_score, 4),
            "is_above_threshold": self.is_above_threshold,
        }


class PotholeValidator:
    """
    Multi-signal pothole event validator.

    Usage:
        validator = PotholeValidator()
        for event in confirmed_events:
            score, signals = validator.score(event, frame_width, frame_height)
            event.composite_score = score
    """

    def __init__(self, config: Optional[PotholeValidatorConfig] = None) -> None:
        self.config = config or PotholeValidatorConfig()

    def score(
        self,
        event,
        frame_width: int,
        frame_height: int,
        bboxes: Optional[List[List[float]]] = None,
    ) -> Tuple[float, ValidationSignals]:
        """
        Score a pothole event using multi-signal composite scoring.

        Parameters
        ----------
        event : UnifiedPotholeEvent or PotholeEvent
            The event to score. Must have: mean_confidence, max_confidence,
            total_detections, span_frames, representative_bbox,
            suppression_reason (optional).
        frame_width, frame_height : int
            Original video dimensions for normalizing bbox geometry.
        bboxes : list of [x1,y1,x2,y2], optional
            Historical bboxes for this event (used for spatial variance).
            If None, spatial_score defaults to a moderate value.

        Returns
        -------
        (composite_score, signals)
        """
        cfg = self.config

        # Signal 1: Model confidence (mean across all detections)
        model_conf = float(getattr(event, "mean_confidence", 0.0))
        model_signal = _clamp(model_conf)

        # Signal 2: Temporal persistence
        total_detections = int(getattr(event, "total_detections", 0))
        span_frames = max(int(getattr(event, "span_frames", 1)), 1)
        temporal_signal = self._temporal_score(total_detections, span_frames)

        # Signal 3: Spatial stability
        spatial_signal = self._spatial_score(bboxes, frame_width, frame_height)

        # Signal 4: Geometry reasonableness
        rep_bbox = getattr(event, "representative_bbox", None)
        geometry_signal = self._geometry_score(rep_bbox, frame_width, frame_height)

        # Signal 5: Detection frequency
        frequency_signal = self._frequency_score(total_detections, span_frames)

        # Vehicle overlap penalty
        suppression_reason = getattr(event, "suppression_reason", None)
        has_vehicle_overlap = suppression_reason is not None and "vehicle" in str(suppression_reason).lower()
        overlap_penalty = cfg.vehicle_overlap_penalty if has_vehicle_overlap else 0.0

        # Composite score
        raw_score = (
            model_signal * cfg.weight_model_confidence
            + temporal_signal * cfg.weight_temporal
            + spatial_signal * cfg.weight_spatial
            + geometry_signal * cfg.weight_geometry
            + frequency_signal * cfg.weight_frequency
        )
        composite = _clamp(raw_score - overlap_penalty)

        is_above_threshold = composite >= cfg.min_incident_score

        signals = ValidationSignals(
            model_confidence=model_signal,
            temporal_score=temporal_signal,
            spatial_score=spatial_signal,
            geometry_score=geometry_signal,
            frequency_score=frequency_signal,
            has_vehicle_overlap=has_vehicle_overlap,
            composite_score=composite,
            is_above_threshold=is_above_threshold,
        )

        logger.debug(
            "Event %s: composite_score=%.3f threshold=%.2f above=%s",
            getattr(event, "event_id", "?"),
            composite,
            cfg.min_incident_score,
            is_above_threshold,
        )

        return composite, signals

    # -----------------------------------------------------------------------
    # Individual signal scorers
    # -----------------------------------------------------------------------

    def _temporal_score(self, total_detections: int, span_frames: int) -> float:
        """
        Score based on how persistently the pothole appeared.

        Signal design:
        - 1 detection in 1 frame → score ≈ 0 (noise)
        - 3+ detections over 5+ frames → score approaches 1

        Uses a sigmoid-like curve to reward persistence.
        """
        if total_detections <= 1:
            return 0.0
        if span_frames < self.config.min_temporal_frames:
            return 0.2  # Partial credit for borderline events

        # Detection density normalized by expected minimum
        density = min(total_detections / max(span_frames, 1), 1.0)
        # Bonus for long-spanning events (up to 10x the minimum)
        span_bonus = min(span_frames / (self.config.min_temporal_frames * 10), 1.0)
        return _clamp(density * 0.7 + span_bonus * 0.3)

    def _spatial_score(
        self,
        bboxes: Optional[List[List[float]]],
        frame_width: int,
        frame_height: int,
    ) -> float:
        """
        Score based on spatial stability of the bbox across frames.

        Low variance in bbox center position → more likely a real stationary pothole.
        High variance → tracking noise or false positives jumping around.

        If bboxes not available, returns a neutral 0.5.
        """
        if not bboxes or len(bboxes) < 2:
            return 0.5  # Neutral — can't compute variance

        # Compute normalized center coordinates
        cx_vals = [(b[0] + b[2]) / (2 * frame_width) for b in bboxes]
        cy_vals = [(b[1] + b[3]) / (2 * frame_height) for b in bboxes]

        n = len(cx_vals)
        mean_cx = sum(cx_vals) / n
        mean_cy = sum(cy_vals) / n

        var_x = sum((x - mean_cx) ** 2 for x in cx_vals) / n
        var_y = sum((y - mean_cy) ** 2 for y in cy_vals) / n
        total_variance = math.sqrt(var_x + var_y)

        # Map variance to score: 0 variance → score=1, high variance → score=0
        # Variance of 0.1 (10% of frame) is considered "high"
        score = max(0.0, 1.0 - (total_variance / 0.10))
        return _clamp(score)

    def _geometry_score(
        self,
        bbox: Optional[List[float]],
        frame_width: int,
        frame_height: int,
    ) -> float:
        """
        Score based on how plausible the bbox geometry is for a pothole.

        Ideal pothole bbox:
        - Not too small (noise), not too large (global artifact)
        - Roughly square or slightly wider than tall
        """
        if not bbox or len(bbox) != 4:
            return 0.5  # Neutral

        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0 or frame_width <= 0 or frame_height <= 0:
            return 0.0

        area_ratio = (w * h) / (frame_width * frame_height)
        aspect = w / h

        # Area score: ideal range [0.001, 0.15] for a pothole
        if area_ratio < self.config.min_area_ratio or area_ratio > self.config.max_area_ratio:
            area_score = 0.0
        else:
            # Peak at 0.02 (2% of frame), decay towards edges
            ideal = 0.02
            distance = abs(math.log10(area_ratio) - math.log10(ideal))
            area_score = max(0.0, 1.0 - distance / 2.0)

        # Aspect score: ideal range [0.5, 3.0]
        if aspect < 0.5 or aspect > 3.0:
            aspect_score = 0.3  # Unusual but not impossible
        else:
            aspect_score = 1.0

        return _clamp(area_score * 0.7 + aspect_score * 0.3)

    def _frequency_score(self, total_detections: int, span_frames: int) -> float:
        """
        Score based on detection density within the event span.

        High frequency (detected in most frames it spans) → more real.
        """
        if span_frames == 0:
            return 0.0
        density = min(total_detections / span_frames, 1.0)
        # Reward high density, but single-frame detections get low score
        if total_detections <= 1:
            return 0.1
        return _clamp(density)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, float(value)))
