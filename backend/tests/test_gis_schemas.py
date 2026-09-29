"""
Urban Watch — Tests for Phase 5 GIS Schemas

Validates: Incident, Vehicle, TrafficWindow, RoadSegment, GPS-optional behavior
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.gis.schemas import (
    Incident,
    Vehicle,
    TrafficWindow,
    RoadSegment,
    GPSLocation,
    IncidentType,
    IncidentStatus,
    SeverityLevel,
    CongestionLevel,
)


# ---------------------------------------------------------------------------
# GPSLocation tests
# ---------------------------------------------------------------------------

class TestGPSLocation:
    def test_valid_gps(self):
        loc = GPSLocation(latitude=18.5204, longitude=73.8567, source="video_metadata")
        assert loc.latitude == 18.5204
        assert loc.longitude == 73.8567

    def test_invalid_latitude(self):
        with pytest.raises(Exception):
            GPSLocation(latitude=91.0, longitude=0.0)  # > 90

    def test_invalid_longitude(self):
        with pytest.raises(Exception):
            GPSLocation(latitude=0.0, longitude=200.0)  # > 180


# ---------------------------------------------------------------------------
# Incident tests
# ---------------------------------------------------------------------------

class TestIncident:
    def test_incident_without_gps_is_valid(self):
        """GPS-less incidents must be valid — never reject due to missing GPS."""
        inc = Incident(
            id="video1:event:42",
            type=IncidentType.POTHOLE,
            class_name="pothole",
            canonical_capability="road_condition",
            confidence=0.87,
            severity=SeverityLevel.MEDIUM,
            timestamp=12.5,
            video_id="video1",
            frame=375,
            gps_available=False,
            gps_location=None,
        )
        assert inc.gps_available is False
        assert inc.gps_location is None
        assert inc.status == IncidentStatus.ACTIVE

    def test_incident_with_gps(self):
        loc = GPSLocation(latitude=18.5, longitude=73.8, source="camera_config")
        inc = Incident(
            id="video1:event:43",
            type=IncidentType.NO_HELMET,
            class_name="nohelmet",
            canonical_capability="safety_violation",
            confidence=0.92,
            severity=SeverityLevel.HIGH,
            timestamp=5.0,
            video_id="video1",
            frame=150,
            gps_available=True,
            gps_location=loc,
        )
        assert inc.gps_available is True
        assert inc.gps_location.latitude == 18.5

    def test_incident_confidence_range(self):
        with pytest.raises(Exception):
            Incident(
                id="x",
                type=IncidentType.POTHOLE,
                class_name="pothole",
                canonical_capability="road_condition",
                confidence=1.5,  # > 1.0 — invalid
                severity=SeverityLevel.LOW,
                timestamp=0.0,
                video_id="v",
                frame=0,
            )

    def test_incident_occurrence_count_default(self):
        inc = Incident(
            id="x",
            type=IncidentType.POTHOLE,
            class_name="pothole",
            canonical_capability="road_condition",
            confidence=0.5,
            severity=SeverityLevel.LOW,
            timestamp=0.0,
            video_id="v",
            frame=0,
        )
        assert inc.occurrence_count == 1

    def test_incident_bbox_optional(self):
        inc = Incident(
            id="x",
            type=IncidentType.POTHOLE,
            class_name="pothole",
            canonical_capability="road_condition",
            confidence=0.5,
            severity=SeverityLevel.LOW,
            timestamp=0.0,
            video_id="v",
            frame=0,
            bbox=[100.0, 200.0, 300.0, 400.0],
        )
        assert inc.bbox == [100.0, 200.0, 300.0, 400.0]


# ---------------------------------------------------------------------------
# Vehicle tests
# ---------------------------------------------------------------------------

class TestVehicle:
    def test_vehicle_without_trajectory(self):
        v = Vehicle(
            track_id=7,
            class_name="car",
            confidence=0.88,
            first_seen_frame=0,
            first_seen_timestamp=0.0,
            last_seen_frame=100,
            last_seen_timestamp=4.0,
            frames_seen=100,
        )
        assert v.trajectory == []
        assert v.estimated_speed_kmh is None
        assert v.gps_available is False

    def test_vehicle_speed_advisory(self):
        """Speed is optional — never required."""
        v = Vehicle(
            track_id=1,
            class_name="motorcycle",
            confidence=0.75,
            first_seen_frame=0,
            first_seen_timestamp=0.0,
            last_seen_frame=50,
            last_seen_timestamp=2.0,
            frames_seen=50,
            estimated_speed_kmh=45.0,
        )
        assert v.estimated_speed_kmh == 45.0


# ---------------------------------------------------------------------------
# TrafficWindow tests
# ---------------------------------------------------------------------------

class TestTrafficWindow:
    def test_basic_traffic_window(self):
        w = TrafficWindow(
            timestamp_start=0.0,
            timestamp_end=5.0,
            vehicle_count=20,
            unique_vehicle_count=12,
            density_level="MEDIUM",
            congestion_score=0.4,
            congestion_level=CongestionLevel.MEDIUM,
        )
        assert w.unique_vehicle_count == 12
        assert w.gps_available is False
        assert w.latitude is None

    def test_congestion_score_bounds(self):
        with pytest.raises(Exception):
            TrafficWindow(
                timestamp_start=0.0,
                timestamp_end=5.0,
                vehicle_count=5,
                unique_vehicle_count=5,
                density_level="LOW",
                congestion_score=1.5,  # > 1.0 — invalid
                congestion_level=CongestionLevel.LOW,
            )


# ---------------------------------------------------------------------------
# RoadSegment tests
# ---------------------------------------------------------------------------

class TestRoadSegment:
    def test_road_segment_without_gps(self):
        seg = RoadSegment(
            id="osm:way:12345",
            pothole_count=3,
            incident_count=4,
            congestion_score=0.4,
            helmet_violation_count=1,
        )
        assert seg.gps_available is False
        assert seg.centroid_lat is None

    def test_risk_score_computation(self):
        seg = RoadSegment(
            id="test:seg:1",
            pothole_count=5,
            incident_count=5,
            congestion_score=0.6,
            helmet_violation_count=2,
        )
        score = seg.compute_risk_score(
            pothole_weight=0.50,
            congestion_weight=0.25,
            safety_weight=0.25,
            max_potholes=10,
            max_violations=5,
        )
        # pothole: 5/10 * 0.50 = 0.25
        # congestion: 0.6 * 0.25 = 0.15
        # safety: 2/5 * 0.25 = 0.10
        # total = 0.50
        assert abs(score - 0.50) < 0.01

    def test_risk_score_clamped(self):
        seg = RoadSegment(
            id="test:seg:2",
            pothole_count=100,
            incident_count=100,
            congestion_score=1.0,
            helmet_violation_count=100,
        )
        score = seg.compute_risk_score()
        assert 0.0 <= score <= 1.0
