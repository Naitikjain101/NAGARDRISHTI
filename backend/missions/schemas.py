"""
Urban Watch — Mission Architecture Schemas

Pydantic models for:
  - MissionMetadata  (inbound JSON when registering a mission)
  - RoutePoint       (a single GPS sample in the timeline)
  - MissionRecord    (what the DB returns)
  - ObservationRecord (raw evidence attached to an incident)
  - TelemetrySnapshot (live state for frontend polling)
"""

from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, field_validator, model_validator
import math


# ── GPS primitives ────────────────────────────────────────────────────────────

class RoutePoint(BaseModel):
    """One GPS sample in the mission timeline."""
    timestamp: float          # seconds into video, ≥ 0
    lat: float                # latitude  [-90,  90]
    lng: float                # longitude [-180, 180]

    @field_validator("timestamp")
    @classmethod
    def ts_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("timestamp must be ≥ 0")
        return v

    @field_validator("lat")
    @classmethod
    def lat_range(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError(f"latitude {v} out of range [-90, 90]")
        return v

    @field_validator("lng")
    @classmethod
    def lng_range(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError(f"longitude {v} out of range [-180, 180]")
        return v


# ── Mission Metadata (inbound from JSON file) ─────────────────────────────────

class MissionMetadata(BaseModel):
    """
    JSON schema for registering a demo mission.

    Example:
        {
          "bus_id": "BUS-104",
          "route_id": "R-01",
          "route_name": "Jaipur City Center Loop",
          "video_filename": "potholes.mp4",
          "duration": 512,
          "gps": [
            {"timestamp": 0, "lat": 26.9124, "lng": 75.7873},
            {"timestamp": 60, "lat": 26.9200, "lng": 75.7950}
          ]
        }
    """
    bus_id:         str
    route_id:       str
    route_name:     str
    video_filename: str          # filename only, not a full path
    duration:       float        # seconds — must be > 0
    gps:            List[RoutePoint]

    @field_validator("bus_id")
    @classmethod
    def bus_id_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("bus_id must not be empty")
        return v.strip()

    @field_validator("gps")
    @classmethod
    def gps_has_min_points(cls, v: List[RoutePoint]) -> List[RoutePoint]:
        if len(v) < 2:
            raise ValueError("gps must contain at least 2 points")
        return v

    @field_validator("duration")
    @classmethod
    def duration_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("duration must be > 0")
        return v

    @model_validator(mode="after")
    def gps_timestamps_ascending(self) -> "MissionMetadata":
        """GPS timestamps must be strictly ascending."""
        times = [p.timestamp for p in self.gps]
        for i in range(1, len(times)):
            if times[i] <= times[i - 1]:
                raise ValueError(
                    f"GPS timestamps must be strictly ascending. "
                    f"Point {i} (ts={times[i]}) ≤ point {i-1} (ts={times[i-1]})"
                )
        return self

    @model_validator(mode="after")
    def gps_within_duration(self) -> "MissionMetadata":
        """All GPS timestamps must be ≤ duration."""
        for p in self.gps:
            if p.timestamp > self.duration:
                raise ValueError(
                    f"GPS point timestamp {p.timestamp}s exceeds mission duration {self.duration}s"
                )
        return self


# ── DB Records (outbound from DB queries) ─────────────────────────────────────

class MissionRecord(BaseModel):
    """Row returned from demo_missions table."""
    id:              str
    bus_id:          str
    route_id:        str
    route_name:      str
    video_filename:  str
    duration_seconds: float
    status:          str
    metadata:        Optional[dict] = None
    created_at:      Optional[str] = None
    updated_at:      Optional[str] = None


class ObservationRecord(BaseModel):
    """Row returned from incident_observations table."""
    id:              str
    incident_id:     str
    mission_id:      Optional[str] = None
    bus_id:          Optional[str] = None
    video_timestamp: Optional[float] = None
    latitude:        Optional[float] = None
    longitude:       Optional[float] = None
    confidence:      Optional[float] = None
    bbox:            Optional[list] = None
    frame_index:     Optional[int] = None
    evidence_url:    Optional[str] = None
    created_at:      Optional[str] = None


# ── Telemetry Snapshot (live state for frontend polling) ──────────────────────

class TelemetrySnapshot(BaseModel):
    """
    Live state object the frontend binds to while a mission plays.
    Returned by GET /api/missions/{id}/telemetry
    """
    mission_id:       str
    bus_id:           str
    route_name:       str
    mode:             Literal["live", "replay"]
    current_timestamp: float          # seconds into video
    current_lat:      Optional[float] = None
    current_lng:      Optional[float] = None
    speed_kmh:        Optional[float] = None   # estimated from GPS delta
    ai_status:        Literal["detecting", "idle", "processing"] = "idle"

    # Running counts this mission
    pothole_count:    int = 0
    waterlogging_count: int = 0
    vehicle_count:    int = 0

    # Most recent event
    last_event_type:       Optional[str] = None
    last_event_severity:   Optional[str] = None
    last_event_timestamp:  Optional[float] = None
    last_event_lat:        Optional[float] = None
    last_event_lng:        Optional[float] = None


# ── Incident with observations (map-facing API response) ─────────────────────

class IncidentWithObservations(BaseModel):
    """Incident row enriched with its observation trail."""
    id:                str
    incident_type:     str
    severity:          str
    status:            str
    confidence:        Optional[float] = None
    latitude:          Optional[float] = None
    longitude:         Optional[float] = None
    observation_count: int = 1
    observed_by:       List[str] = []
    dedup_status:      str = "PENDING"
    first_seen_at:     Optional[str] = None
    last_seen_at:      Optional[str] = None
    source_mission_id: Optional[str] = None
    observations:      List[ObservationRecord] = []
