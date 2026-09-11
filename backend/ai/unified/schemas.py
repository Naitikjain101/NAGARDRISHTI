"""
Urban Watch — Phase 3 Unified AI Schemas

Defines the output structure for the Road-Aware Pothole Intelligence integration.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ai.common.schemas import (
    VideoMetadata, 
    ProcessingConfig, 
    TrackResult,
    VehicleCountSummary,
    DensityWindow
)
from ai.pothole.schemas import PotholeDetection
from ai.waterlogging.schemas import WaterloggingDetection


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    RAW = "raw"
    CANDIDATE = "candidate"
    PERSISTING = "persisting"
    CONFIRMED = "confirmed"
    SUPPRESSED = "suppressed"
    REJECTED_ROI = "rejected_roi"
    REJECTED_GEOMETRY = "rejected_geometry"
    REJECTED_TEMPORAL = "rejected_temporal"
    RESOLVED = "resolved"


class Location(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    

class RejectionStats(BaseModel):
    total_raw: int = 0
    rejected_roi: int = 0
    rejected_geometry: int = 0
    rejected_low_confidence: int = 0
    rejected_vehicle_overlap: int = 0
    rejected_temporal_noise: int = 0


class UnifiedPotholeEvent(BaseModel):
    """
    A tracked physical pothole across consecutive video frames, enriched with severity and interaction logic.
    """
    event_id: int
    event_type: str = "pothole"  # pothole, helmet, no_helmet
    status: EventStatus
    
    # Temporal
    first_seen_frame: int
    first_seen_timestamp: float
    first_seen: Optional[str] = None  # ISO8601
    last_seen_frame: int
    last_seen_timestamp: float
    last_seen: Optional[str] = None  # ISO8601
    
    total_detections: int
    span_frames: int
    stability_score: float = Field(ge=0.0, le=1.0)
    max_confidence: float = Field(ge=0.0, le=1.0)
    mean_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    representative_bbox: List[float] = Field(min_length=4, max_length=4)
    estimated_severity: SeverityLevel
    
    gps_location: Optional[Location] = None
    
    # Interaction debugging metadata
    suppression_reason: Optional[str] = None
    overlapping_vehicle_track_id: Optional[int] = None


class UnifiedWaterloggingEvent(BaseModel):
    """
    A tracked waterlogging event across consecutive video frames, enriched with severity.
    """
    event_id: int
    event_type: str = "waterlogging"
    status: EventStatus
    
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    
    total_detections: int
    span_frames: int
    stability_score: float = Field(ge=0.0, le=1.0)
    max_confidence: float = Field(ge=0.0, le=1.0)
    mean_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    representative_bbox: List[float] = Field(min_length=4, max_length=4)
    max_area_ratio: float = Field(ge=0.0, le=1.0)
    last_polygon: List[List[float]] = Field(default_factory=list)
    estimated_severity: SeverityLevel
    
    gps_location: Optional[Location] = None


class UnifiedFrameResult(BaseModel):
    """
    Fused AI result for a single video frame containing both vehicle and pothole intelligence.
    """
    frame_index: int
    timestamp: float
    
    # Vehicle Intelligence
    vehicle_tracks: List[TrackResult] = Field(default_factory=list)
    unique_vehicle_count_in_frame: int = 0
    
    # Pothole Intelligence
    pothole_detections: List[PotholeDetection] = Field(default_factory=list)
    active_pothole_event_ids: List[int] = Field(default_factory=list)

    # Waterlogging Intelligence
    waterlogging_detections: List[WaterloggingDetection] = Field(default_factory=list)
    active_waterlogging_event_ids: List[int] = Field(default_factory=list)


class UnifiedVideoSummary(BaseModel):
    """
    The final complete output generated after processing an entire video via the unified pipeline.
    """
    video: VideoMetadata
    processing: ProcessingConfig
    status: str
    error: Optional[str] = None
    
    # Frame-by-frame detailed fusion
    frames: List[UnifiedFrameResult] = Field(default_factory=list)
    
    # Phase 1: Traffic Aggregations
    vehicle_counts: Optional[VehicleCountSummary] = None
    density_windows: List[DensityWindow] = Field(default_factory=list)
    
    # Phase 3: Road-Aware Pothole Events
    pothole_events: List[UnifiedPotholeEvent] = Field(default_factory=list)

    # Phase 5: Waterlogging Events
    waterlogging_events: List[UnifiedWaterloggingEvent] = Field(default_factory=list)
    
    timing: Dict[str, Any] = Field(default_factory=dict)
