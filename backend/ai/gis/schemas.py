"""
Urban Watch — Phase 5 GIS / Geospatial Data Schemas

Robust geospatial data model for incidents, vehicles, traffic windows,
and road segments.

CRITICAL RULES:
- GPS is ALWAYS optional. Never fabricate coordinates.
- If a video has no GPS metadata: mark gps_available=False, omit lat/lon.
- Incidents remain valid without GPS.
- All geospatial fields use Optional[float] — not fabricated defaults.

Python 3.9 compatible: uses Optional[T] and List[T].
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class IncidentType(str, Enum):
    POTHOLE = "pothole"
    NO_HELMET = "no_helmet"
    HELMET = "helmet"
    TRAFFIC_CONGESTION = "traffic_congestion"
    VEHICLE_INCIDENT = "vehicle_incident"
    OTHER = "other"


class IncidentStatus(str, Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    SUPPRESSED = "suppressed"
    REJECTED = "rejected"
    RESOLVED = "resolved"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class CongestionLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class GPSAccuracy(str, Enum):
    HIGH = "high"        # < 5 m accuracy (e.g., differential GPS)
    MEDIUM = "medium"    # 5-20 m accuracy (e.g., standard GPS)
    LOW = "low"          # > 20 m accuracy (e.g., cell tower)
    APPROXIMATE = "approximate"  # Manually assigned camera location
    UNAVAILABLE = "unavailable"  # No GPS data


# ---------------------------------------------------------------------------
# GPS Location — Always Optional
# ---------------------------------------------------------------------------

class GPSLocation(BaseModel):
    """
    GPS coordinates — NEVER fabricated.

    If GPS is unavailable, this object should NOT be created.
    The parent schema's gps_location field must remain None.
    """
    latitude: float = Field(
        ge=-90.0, le=90.0,
        description="WGS84 latitude in decimal degrees"
    )
    longitude: float = Field(
        ge=-180.0, le=180.0,
        description="WGS84 longitude in decimal degrees"
    )
    accuracy_meters: Optional[float] = Field(
        default=None, ge=0.0,
        description="GPS accuracy radius in meters (None if unknown)"
    )
    accuracy_class: GPSAccuracy = GPSAccuracy.UNAVAILABLE
    altitude_meters: Optional[float] = Field(
        default=None,
        description="Altitude above sea level in meters (None if unknown)"
    )
    source: str = Field(
        default="unknown",
        description="GPS source: 'video_metadata', 'camera_config', 'manual'"
    )

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Incident — Core event schema
# ---------------------------------------------------------------------------

class Incident(BaseModel):
    """
    A validated, deduplicated urban incident.

    This is the canonical output of the Phase 5 AI pipeline.
    GPS is always optional — incidents are valid without coordinates.
    """

    id: str = Field(description="Unique incident ID (UUID or video_id:event_id)")
    type: IncidentType
    class_name: str = Field(description="Raw AI class name (pothole, no_helmet, etc.)")
    canonical_capability: str = Field(
        description="High-level capability: road_condition, safety_violation, traffic"
    )

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0, description="AI model confidence")
    composite_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Multi-signal composite confidence from PotholeValidator"
    )

    # Severity
    severity: SeverityLevel = SeverityLevel.UNKNOWN

    # Temporal
    timestamp: float = Field(description="Video timestamp in seconds when first observed")
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    occurrence_count: int = Field(default=1, ge=1, description="Total detections grouped into this incident")

    # Source
    video_id: str
    frame: int = Field(description="Frame index of first detection")
    track_id: Optional[int] = Field(default=None, description="Track ID if tracking was active")
    source: str = Field(default="ai_detection", description="Detection source")

    # Bounding box (in original video pixels)
    bbox: Optional[List[float]] = Field(
        default=None, min_length=4, max_length=4,
        description="[x1, y1, x2, y2] in original video pixel coordinates"
    )

    # GPS — ALWAYS OPTIONAL
    gps_available: bool = Field(default=False, description="True only when real GPS data exists")
    gps_location: Optional[GPSLocation] = Field(
        default=None,
        description="GPS coordinates — None if GPS unavailable. NEVER fabricated."
    )

    # Road context
    road_segment_id: Optional[str] = None

    # Status and filtering
    status: IncidentStatus = IncidentStatus.ACTIVE
    suppression_reason: Optional[str] = None

    # Additional metadata
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# Vehicle — Tracked vehicle
# ---------------------------------------------------------------------------

class VehicleTrajectoryPoint(BaseModel):
    """A single point in a vehicle's trajectory."""
    frame_index: int
    timestamp: float
    bbox: List[float] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)


class Vehicle(BaseModel):
    """
    A tracked vehicle across a video sequence.

    trajectory is downsampled — not stored for every frame.
    estimated_speed is advisory only: never claimed as accurate.
    """
    track_id: int
    class_name: str = Field(description="Vehicle class: car, motorcycle, bus, truck, bicycle")
    confidence: float = Field(ge=0.0, le=1.0)

    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    frames_seen: int = Field(ge=1)

    # Trajectory (downsampled, not every frame)
    trajectory: List[VehicleTrajectoryPoint] = Field(
        default_factory=list,
        description="Downsampled trajectory points. Empty if trajectory not tracked."
    )

    # Speed (advisory only — never physically calibrated)
    estimated_speed_kmh: Optional[float] = Field(
        default=None,
        description=(
            "Advisory speed estimate in km/h. "
            "NOT physically calibrated. Requires camera intrinsics + GPS scale. "
            "Use only as relative indicator."
        )
    )

    # GPS
    gps_available: bool = False
    gps_location: Optional[GPSLocation] = None

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# TrafficWindow — Aggregated traffic measurement
# ---------------------------------------------------------------------------

class TrafficWindow(BaseModel):
    """
    Aggregated traffic density for a rolling time window.

    vehicle_count = unique persistent track IDs (NOT raw detection count).
    congestion_score is a normalized [0, 1] metric — not calibrated engineering data.
    """
    timestamp_start: float = Field(description="Window start in video seconds")
    timestamp_end: float = Field(description="Window end in video seconds")

    # GPS of the camera/sensor — optional
    gps_available: bool = False
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    # Traffic metrics
    vehicle_count: int = Field(ge=0, description="Total detections in window (including duplicates)")
    unique_vehicle_count: int = Field(ge=0, description="Unique persistent track IDs in window")
    by_class: Dict[str, int] = Field(
        default_factory=dict,
        description="Unique vehicle count per class"
    )

    # Derived density
    density_level: str = Field(description="LOW / MEDIUM / HIGH / SEVERE")
    congestion_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description=(
            "Normalized congestion score [0, 1]. "
            "0 = no traffic, 1 = maximum observed density. "
            "NOT calibrated traffic engineering data."
        )
    )
    congestion_level: CongestionLevel = CongestionLevel.UNKNOWN

    # Context note attached to every window
    note: str = Field(
        default=(
            "Prototype traffic-density classification based on tracked "
            "vehicle counts. NOT calibrated traffic engineering data. "
            "Thresholds configurable in backend/ai/common/config.py."
        )
    )

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# RoadSegment — Aggregated road-level risk score
# ---------------------------------------------------------------------------

class RoadSegment(BaseModel):
    """
    Aggregated road condition data for a segment.

    risk_score is an AI-derived operational indicator — NOT scientifically validated.
    Clearly labeled as such in the UI.
    """
    id: str = Field(description="Road segment ID (e.g., OSM way ID or custom)")
    name: Optional[str] = None

    # Geometry — GeoJSON LineString coordinates [[lon, lat], ...]
    # Optional because we may have incidents without road geometry
    geometry: Optional[List[List[float]]] = Field(
        default=None,
        description="GeoJSON LineString coordinate pairs [[lon, lat], ...]"
    )

    # GPS centroid (optional)
    gps_available: bool = False
    centroid_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    centroid_lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    # Aggregated metrics
    incident_count: int = Field(default=0, ge=0)
    pothole_count: int = Field(default=0, ge=0)
    congestion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    helmet_violation_count: int = Field(default=0, ge=0)

    # Risk score (AI-derived, not scientifically validated)
    risk_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description=(
            "AI-derived operational risk score [0, 1]. "
            "Weighted combination of pothole count, congestion, safety violations. "
            "NOT scientifically validated. Use as relative operational indicator only."
        )
    )

    last_observed: Optional[float] = Field(
        default=None,
        description="Video timestamp of most recent observation"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Average AI confidence for incidents on this segment"
    )

    # Risk label (human-readable)
    risk_label: str = Field(default="UNKNOWN")

    model_config = {"frozen": False}

    def compute_risk_score(
        self,
        pothole_weight: float = 0.50,
        congestion_weight: float = 0.25,
        safety_weight: float = 0.25,
        max_potholes: int = 10,
        max_violations: int = 5,
    ) -> float:
        """
        Compute a composite risk score.

        All weights are configurable — see Phase 5 config.
        This is NOT a scientifically validated formula.
        """
        pothole_contribution = min(self.pothole_count / max(max_potholes, 1), 1.0) * pothole_weight
        congestion_contribution = self.congestion_score * congestion_weight
        safety_contribution = (
            min(self.helmet_violation_count / max(max_violations, 1), 1.0) * safety_weight
        )
        score = pothole_contribution + congestion_contribution + safety_contribution
        return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# API Response Schemas for Phase 5
# ---------------------------------------------------------------------------

class IncidentListResponse(BaseModel):
    """Paginated incident list response."""
    incidents: List[Incident]
    total: int
    page: int = 1
    page_size: int = 50
    gps_note: str = Field(
        default=(
            "GPS coordinates are only present when real GPS data exists in the source video. "
            "Incidents without GPS remain valid and are NOT assigned fabricated coordinates."
        )
    )


class TrafficCurrentResponse(BaseModel):
    """Current traffic state snapshot."""
    timestamp: float
    active_vehicles: int
    density_level: str
    congestion_score: float
    congestion_level: CongestionLevel
    by_class: Dict[str, int]
    gps_available: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TrafficHeatmapPoint(BaseModel):
    """A single heatmap data point for map rendering."""
    latitude: float
    longitude: float
    weight: float = Field(ge=0.0, le=1.0, description="Intensity: congestion_score")
    vehicle_count: int
    timestamp: float


class TrafficHeatmapResponse(BaseModel):
    """Heatmap data for a time range."""
    time_range: str  # "5min", "15min", "1hour", "today"
    points: List[TrafficHeatmapPoint]
    note: str = Field(
        default=(
            "Heatmap requires GPS-tagged camera locations. "
            "Points without GPS are omitted."
        )
    )


class RoadConditionsResponse(BaseModel):
    """Road condition layer data."""
    segments: List[RoadSegment]
    risk_score_note: str = Field(
        default=(
            "Road risk scores are AI-derived operational indicators. "
            "They are NOT scientifically validated or calibrated to engineering standards."
        )
    )


class SystemStatusResponse(BaseModel):
    """Overall system status."""
    status: str
    phase: str = "5"
    device: str
    device_name: Optional[str]
    cuda_available: bool
    mps_available: bool
    torch_version: str
    ultralytics_version: Optional[str]
    active_processing: int = Field(default=0, description="Number of videos currently processing")
    total_incidents: int = 0
    total_videos: int = 0
