"""
Unit tests for GPS Interpolation Engine.
Run: python3 -m pytest backend/tests/test_gps_interpolation.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import pytest
from ai.gis.interpolator import InterpolationEngine, haversine_distance_m

# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_ROUTE = [
    {"timestamp": 0,   "lat": 26.9124, "lng": 75.7873},
    {"timestamp": 60,  "lat": 26.9200, "lng": 75.7950},
    {"timestamp": 120, "lat": 26.9280, "lng": 75.8020},
    {"timestamp": 180, "lat": 26.9350, "lng": 75.8100},
]

@pytest.fixture
def engine():
    return InterpolationEngine(SIMPLE_ROUTE)


# ── Boundary clamping ─────────────────────────────────────────────────────────

def test_clamp_before_start(engine):
    lat, lng = engine.position_at(-10)
    assert (lat, lng) == (26.9124, 75.7873), "Should return first point for t < 0"

def test_clamp_after_end(engine):
    lat, lng = engine.position_at(999)
    assert (lat, lng) == (26.9350, 75.8100), "Should return last point for t > duration"

def test_exact_start(engine):
    lat, lng = engine.position_at(0)
    assert lat == pytest.approx(26.9124)
    assert lng == pytest.approx(75.7873)

def test_exact_end(engine):
    lat, lng = engine.position_at(180)
    assert lat == pytest.approx(26.9350)
    assert lng == pytest.approx(75.8100)


# ── Midpoint interpolation ────────────────────────────────────────────────────

def test_midpoint_first_segment(engine):
    """t=30 is exactly halfway through the first segment [0→60]."""
    lat, lng = engine.position_at(30)
    expected_lat = (26.9124 + 26.9200) / 2
    expected_lng = (75.7873 + 75.7950) / 2
    assert lat == pytest.approx(expected_lat, rel=1e-6)
    assert lng == pytest.approx(expected_lng, rel=1e-6)

def test_midpoint_second_segment(engine):
    """t=90 is exactly halfway through segment [60→120]."""
    lat, lng = engine.position_at(90)
    expected_lat = (26.9200 + 26.9280) / 2
    expected_lng = (75.7950 + 75.8020) / 2
    assert lat == pytest.approx(expected_lat, rel=1e-6)
    assert lng == pytest.approx(expected_lng, rel=1e-6)

def test_at_waypoint(engine):
    """t=60 should land exactly on the second waypoint."""
    lat, lng = engine.position_at(60)
    assert lat == pytest.approx(26.9200)
    assert lng == pytest.approx(75.7950)


# ── Monotonicity ──────────────────────────────────────────────────────────────

def test_lat_monotonically_increasing(engine):
    """For this northbound route, lat should increase monotonically."""
    timestamps = [0, 30, 60, 90, 120, 150, 180]
    lats = [engine.position_at(t)[0] for t in timestamps]
    for i in range(1, len(lats)):
        assert lats[i] >= lats[i - 1], f"Lat not increasing at t={timestamps[i]}"


# ── Smoothstep ────────────────────────────────────────────────────────────────

def test_smoothstep_clamps_same_as_linear(engine):
    assert engine.position_at_smoothstep(-5)  == engine.position_at(-5)
    assert engine.position_at_smoothstep(999) == engine.position_at(999)

def test_smoothstep_midpoint_different_from_linear(engine):
    """Smoothstep at t=30 should differ slightly from linear."""
    lin = engine.position_at(30)
    smo = engine.position_at_smoothstep(30)
    # At exact midpoint (t=0.5), smoothstep == linear, so test off-midpoint
    lin2 = engine.position_at(20)
    smo2 = engine.position_at_smoothstep(20)
    # They'll differ because smoothstep compresses the early part
    assert lin2 != smo2 or lin != smo  # at least one pair differs


# ── Speed estimation ──────────────────────────────────────────────────────────

def test_speed_at_midpoint(engine):
    """Speed should be a positive finite number for a moving bus."""
    speed = engine.speed_at(30)
    assert speed is not None
    assert speed > 0
    assert math.isfinite(speed)

def test_speed_in_reasonable_range():
    """A bus covering ~1km in 60s should be ~60 km/h."""
    # Route: ~1km northward in 60 seconds
    route = [
        {"timestamp": 0,  "lat": 26.9000, "lng": 75.8000},
        {"timestamp": 60, "lat": 26.9090, "lng": 75.8000},  # ~1km north
    ]
    eng = InterpolationEngine(route)
    speed = eng.speed_at(30)
    # 1km in 60s = ~60 km/h, allow ±20%
    assert 40 < speed < 80, f"Expected ~60 km/h, got {speed:.1f}"


# ── Validation ────────────────────────────────────────────────────────────────

def test_requires_at_least_two_points():
    with pytest.raises(ValueError, match="at least 2"):
        InterpolationEngine([{"timestamp": 0, "lat": 26.9, "lng": 75.8}])

def test_rejects_duplicate_timestamps():
    """Duplicate timestamps (after sorting) should raise, not silently corrupt."""
    with pytest.raises(ValueError):
        InterpolationEngine([
            {"timestamp": 0,  "lat": 26.9,  "lng": 75.8},
            {"timestamp": 10, "lat": 26.91, "lng": 75.81},
            {"timestamp": 10, "lat": 26.92, "lng": 75.82},  # ← duplicate ts
        ])


# ── Haversine ─────────────────────────────────────────────────────────────────

def test_haversine_same_point():
    d = haversine_distance_m(26.9124, 75.7873, 26.9124, 75.7873)
    assert d == pytest.approx(0.0, abs=1e-6)

def test_haversine_known_distance():
    """Jaipur to Amber Fort is roughly 11 km."""
    d = haversine_distance_m(26.9124, 75.7873, 26.9855, 75.8513)
    assert 9_000 < d < 13_000, f"Expected ~11km, got {d/1000:.2f}km"


# ── Properties ────────────────────────────────────────────────────────────────

def test_properties(engine):
    assert engine.start_position == (26.9124, 75.7873)
    assert engine.end_position   == (26.9350, 75.8100)
    assert engine.total_duration == 180
    assert engine.waypoint_count == 4
