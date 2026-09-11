"""
Urban Watch — Phase 5 Unified Event Engine

Wraps the PotholeEventTracker to inject:
1. Intelligent Road Surface ROI Filtering
2. Geometric Heuristic Filtering
3. Advanced Vehicle Interaction Suppression
4. Multi-class Severity Assignment
5. Forensic Accounting (RejectionStats)
"""

from typing import List, Dict, Optional
import logging

from ai.pothole.tracker import PotholeEventTracker
from ai.pothole.schemas import PotholeDetection
from ai.common.schemas import TrackResult
from ai.common.config import (
    ROAD_ROI_POLYGON,
    POTHOLE_MIN_ROI_OVERLAP,
    POTHOLE_MIN_AREA_RATIO,
    POTHOLE_MAX_AREA_RATIO,
    POTHOLE_MIN_ASPECT_RATIO,
    POTHOLE_MAX_ASPECT_RATIO,
)
from ai.unified.schemas import UnifiedPotholeEvent, EventStatus, SeverityLevel, RejectionStats
from ai.unified.interaction import VehicleInteractionSuppressor
from ai.unified.filters import RoadROIFilter, GeometryFilter
from ai.unified.severity import SeverityCalculator

logger = logging.getLogger(__name__)

class UnifiedEventEngine:
    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        tracker_kwargs: dict = None,
    ) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Core temporal tracker
        self.tracker = PotholeEventTracker(**(tracker_kwargs or {}))
        
        # Phase 5 Intelligence Layers
        self.roi_filter = RoadROIFilter(
            roi_polygon=ROAD_ROI_POLYGON, 
            min_overlap=POTHOLE_MIN_ROI_OVERLAP
        )
        self.geometry_filter = GeometryFilter(
            min_area_ratio=POTHOLE_MIN_AREA_RATIO,
            max_area_ratio=POTHOLE_MAX_AREA_RATIO,
            min_aspect_ratio=POTHOLE_MIN_ASPECT_RATIO,
            max_aspect_ratio=POTHOLE_MAX_ASPECT_RATIO,
        )
        self.interaction_suppressor = VehicleInteractionSuppressor()
        
        # Forensic tracking
        self.rejection_stats = RejectionStats()
        
        # Store metadata per event
        self._event_metadata: Dict[int, Dict] = {}

    def update(
        self,
        frame_index: int,
        timestamp: float,
        raw_detections: List[PotholeDetection],
        vehicle_tracks: List[TrackResult]
    ) -> List[int]:
        """
        Filters detections BEFORE sending them to the temporal tracker.
        Returns active event IDs.
        """
        self.rejection_stats.total_raw += len(raw_detections)
        filtered_detections: List[PotholeDetection] = []
        
        # 1. Pre-tracker Filtering
        for det in raw_detections:
            # A. ROI Filter
            is_rejected_roi, reason_roi = self.roi_filter.evaluate(det, self.frame_width, self.frame_height)
            if is_rejected_roi:
                self.rejection_stats.rejected_roi += 1
                continue
                
            # B. Geometry Filter
            is_rejected_geom, reason_geom = self.geometry_filter.evaluate(det, self.frame_width, self.frame_height)
            if is_rejected_geom:
                self.rejection_stats.rejected_geometry += 1
                continue
                
            filtered_detections.append(det)
            
        # 2. Update Temporal Tracker
        active_ids = self.tracker.update(frame_index, timestamp, filtered_detections)
        
        # 3. Post-tracker (Event-level) Filtering (Interaction Suppression)
        for ev_dict in self.tracker._active_events:
            ev_id = ev_dict["id"]
            if ev_id not in self._event_metadata:
                self._event_metadata[ev_id] = {
                    "suppression_reason": None,
                    "overlapping_vehicle_track_id": None,
                }
            
            # Re-evaluate interaction based on latest box
            last_box = ev_dict["last_bbox"]
            dummy_det = PotholeDetection(confidence=ev_dict["max_confidence"], bbox=last_box)
            
            is_suppressed, reason, track_id = self.interaction_suppressor.evaluate_intersection(
                dummy_det, vehicle_tracks
            )
            
            if is_suppressed:
                if self._event_metadata[ev_id]["suppression_reason"] is None:
                    self.rejection_stats.rejected_vehicle_overlap += 1
                self._event_metadata[ev_id]["suppression_reason"] = reason
                self._event_metadata[ev_id]["overlapping_vehicle_track_id"] = track_id
                
        return active_ids

    def finalize(self) -> List[UnifiedPotholeEvent]:
        """Finalize tracking and return unified events."""
        phase2_events = self.tracker.finalize()
        unified = []
        for e in phase2_events:
            event = self._enrich_event(e)
            # Track temporal rejections
            if event.status == EventStatus.REJECTED_TEMPORAL:
                self.rejection_stats.rejected_temporal_noise += 1
            unified.append(event)
        return unified
        
    def get_unified_events(self) -> List[UnifiedPotholeEvent]:
        """Returns currently completed unified events."""
        return [self._enrich_event(e) for e in self.tracker._completed_events]

    def _enrich_event(self, event) -> UnifiedPotholeEvent:
        meta = self._event_metadata.get(event.event_id, {})
        
        # Determine Status
        status = EventStatus.CANDIDATE
        if meta.get("suppression_reason"):
            status = EventStatus.SUPPRESSED
        elif event.is_confirmed:
            status = EventStatus.CONFIRMED
        else:
            status = EventStatus.REJECTED_TEMPORAL

        # Determine Severity
        severity = SeverityCalculator.calculate(
            event.representative_bbox,
            self.frame_width,
            self.frame_height
        )

        return UnifiedPotholeEvent(
            event_id=event.event_id,
            status=status,
            first_seen_frame=event.first_seen_frame,
            first_seen_timestamp=event.first_seen_timestamp,
            last_seen_frame=event.last_seen_frame,
            last_seen_timestamp=event.last_seen_timestamp,
            total_detections=event.total_detections,
            span_frames=event.span_frames,
            stability_score=event.stability_score,
            max_confidence=event.max_confidence,
            mean_confidence=event.mean_confidence,
            representative_bbox=event.representative_bbox,
            estimated_severity=severity,
            suppression_reason=meta.get("suppression_reason"),
            overlapping_vehicle_track_id=meta.get("overlapping_vehicle_track_id")
        )

from ai.waterlogging.tracker import WaterloggingEventTracker
from ai.waterlogging.schemas import WaterloggingDetection
from ai.waterlogging.severity import WaterloggingSeverityCalculator
from ai.waterlogging.validator import WaterloggingValidator, ValidationConfig
from ai.unified.schemas import UnifiedWaterloggingEvent

class WaterloggingEventEngine:
    """Temporal tracking and validation engine specifically for waterlogging.
    
    Pipeline (Steps 10/11): RAW DETECTION → VALIDATION → TEMPORAL CONFIRMATION
    → SPATIAL DEDUPLICATION → CONFIRMED WATERLOGGING EVENT → SUPABASE INCIDENT
    """
    
    def __init__(self, frame_width: int, frame_height: int, tracker_kwargs: dict = None,
                 validation_config: ValidationConfig = None) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        self.tracker = WaterloggingEventTracker(**(tracker_kwargs or {}))
        self.severity_calculator = WaterloggingSeverityCalculator()
        self.rejection_stats = RejectionStats()
        
        # Step 11: Validator — sits between raw model output and temporal tracker
        self.validator = WaterloggingValidator(config=validation_config)
        
        # Step 21: Forensic accumulator — rejected detections are never silently dropped
        self.forensic_rejected_detections: list = []  # {frame_index, detection, reasons}
        self.forensic_raw_count: int = 0
        self.forensic_validated_count: int = 0

    def update(
        self,
        frame_index: int,
        timestamp: float,
        raw_detections: List[WaterloggingDetection],
        vehicle_tracks: List[TrackResult]
    ) -> List[int]:
        self.rejection_stats.total_raw += len(raw_detections)
        self.forensic_raw_count += len(raw_detections)
        
        # Step 11: VALIDATION — filter before temporal tracker
        accepted_detections, validation_results = self.validator.validate_batch(
            raw_detections, self.frame_width, self.frame_height
        )
        
        self.forensic_validated_count += len(accepted_detections)
        
        # Step 21: Record rejected detections for forensic/debug mode
        for det, result in zip(raw_detections, validation_results):
            if not result.accepted:
                self.forensic_rejected_detections.append({
                    "frame_index": frame_index,
                    "timestamp": timestamp,
                    "confidence": det.confidence,
                    "bbox": det.bbox,
                    "rejection_reasons": [r.value for r in result.rejection_reasons],
                    "validation_score": result.validation_score,
                    "debug_info": result.debug_info,
                })
        
        active_ids = self.tracker.update(frame_index, timestamp, accepted_detections)
        return active_ids

    def finalize(self) -> List[UnifiedWaterloggingEvent]:
        raw_events = self.tracker.get_events(flush=True)
        return [self._enrich_event(e) for e in raw_events]
        
    def get_unified_events(self) -> List[UnifiedWaterloggingEvent]:
        return [self._enrich_event(e) for e in self.tracker.get_events(flush=False)]

    def get_forensic_report(self) -> dict:
        """Step 21: Returns debug/forensic breakdown without creating production incidents."""
        finalized = self.tracker.get_events(flush=False)
        confirmed = [e for e in finalized if e["detections_count"] >= self.tracker.min_event_frames]
        validator_stats = self.validator.get_stats()
        return {
            "raw_detections": self.forensic_raw_count,
            "validated_detections": self.forensic_validated_count,
            "rejected_detections": self.forensic_raw_count - self.forensic_validated_count,
            "confirmed_events": len(confirmed),
            "active_events": len(self.tracker._active_events),
            "completed_events": len(self.tracker._completed_events),
            "rejection_counts": validator_stats["rejection_counts"],
            "rejected_sample": self.forensic_rejected_detections[:10],  # First 10 for inspection
        }

    def _enrich_event(self, event_dict) -> UnifiedWaterloggingEvent:
        status = EventStatus.CONFIRMED if event_dict["detections_count"] >= self.tracker.min_event_frames else EventStatus.REJECTED_TEMPORAL
        if status == EventStatus.REJECTED_TEMPORAL:
            self.rejection_stats.rejected_temporal_noise += 1
            
        severity = self.severity_calculator.calculate(
            max_area_ratio=event_dict.get("max_area_ratio", 0.0),
            stability_score=event_dict.get("stability_score", 0.0),
            max_confidence=event_dict.get("max_confidence", 0.0)
        )

        return UnifiedWaterloggingEvent(
            event_id=event_dict["id"],
            status=status,
            first_seen_frame=event_dict["first_frame"],
            first_seen_timestamp=event_dict["first_timestamp"],
            last_seen_frame=event_dict["last_frame"],
            last_seen_timestamp=event_dict["last_timestamp"],
            total_detections=event_dict["detections_count"],
            span_frames=event_dict["last_frame"] - event_dict["first_frame"] + 1,
            stability_score=event_dict.get("stability_score", 0.0),
            max_confidence=event_dict.get("max_confidence", 0.0),
            mean_confidence=event_dict.get("mean_confidence", 0.0),
            representative_bbox=event_dict["representative_bbox"],
            max_area_ratio=event_dict.get("max_area_ratio", 0.0),
            last_polygon=event_dict.get("last_polygon", []),
            estimated_severity=severity
        )

