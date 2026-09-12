"""
Urban Watch — GPS Interpolation Engine

Given a GPS timeline (list of {timestamp, lat, lng} points),
resolves any video timestamp to a lat/lng via linear interpolation.

Usage:
    from ai.gis.interpolator import InterpolationEngine
    engine = InterpolationEngine(route_points)
    lat, lng = engine.position_at(124.5)

Design:
    - Clamps to start/end for out-of-range timestamps
    - Pure function, no I/O — fully unit-testable
    - Optional easing (linear by default, smoothstep available)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass(frozen=True)
class GPSPoint:
    timestamp: float  # seconds into video
    lat: float
    lng: float


class InterpolationEngine:
    """
    Interpolates GPS position from a sparse timeline of waypoints.

    Accepts either GPSPoint objects or dicts with keys
    {timestamp/ts, lat/latitude, lng/longitude}.
    """

    def __init__(self, points: List) -> None:
        if len(points) < 2:
            raise ValueError("InterpolationEngine requires at least 2 GPS points")

        parsed: List[GPSPoint] = []
        for p in points:
            if isinstance(p, GPSPoint):
                parsed.append(p)
            elif isinstance(p, dict):
                ts  = p.get("timestamp") if p.get("timestamp") is not None else \
                      p.get("ts") if p.get("ts") is not None else \
                      p.get("timestamp_seconds")
                lat = p.get("lat") if p.get("lat") is not None else p.get("latitude")
                lng = p.get("lng") if p.get("lng") is not None else p.get("longitude")
                if ts is None or lat is None or lng is None:
                    raise ValueError(f"GPS point missing required fields: {p}")
                parsed.append(GPSPoint(float(ts), float(lat), float(lng)))
            else:
                raise TypeError(f"Unsupported GPS point type: {type(p)}")

        # Sort by timestamp and validate strictly ascending
        parsed.sort(key=lambda p: p.timestamp)
        for i in range(1, len(parsed)):
            if parsed[i].timestamp <= parsed[i - 1].timestamp:
                raise ValueError(
                    f"GPS timestamps must be strictly ascending after sort. "
                    f"Found duplicate/equal at index {i}: {parsed[i].timestamp}"
                )

        self._points = parsed

    # ── Public API ──────────────────────────────────────────────────────────────

    def position_at(self, timestamp: float) -> Tuple[float, float]:
        """
        Return (lat, lng) at the given video timestamp (seconds).

        - If timestamp < first point: returns first point's position
        - If timestamp > last point:  returns last point's position
        - Otherwise: linearly interpolates between the two bracketing points
        """
        points = self._points

        # Clamp to bounds
        if timestamp <= points[0].timestamp:
            return points[0].lat, points[0].lng
        if timestamp >= points[-1].timestamp:
            return points[-1].lat, points[-1].lng

        # Binary search for bracketing segment
        lo, hi = 0, len(points) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if points[mid].timestamp <= timestamp:
                lo = mid
            else:
                hi = mid

        a, b = points[lo], points[hi]
        t = (timestamp - a.timestamp) / (b.timestamp - a.timestamp)  # [0, 1]

        lat = a.lat + t * (b.lat - a.lat)
        lng = a.lng + t * (b.lng - a.lng)
        return lat, lng

    def position_at_smoothstep(self, timestamp: float) -> Tuple[float, float]:
        """
        Same as position_at() but uses smoothstep easing for slightly more
        natural bus movement (less abrupt direction changes at waypoints).
        """
        points = self._points
        if timestamp <= points[0].timestamp:
            return points[0].lat, points[0].lng
        if timestamp >= points[-1].timestamp:
            return points[-1].lat, points[-1].lng

        lo, hi = 0, len(points) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if points[mid].timestamp <= timestamp:
                lo = mid
            else:
                hi = mid

        a, b = points[lo], points[hi]
        t = (timestamp - a.timestamp) / (b.timestamp - a.timestamp)
        t = t * t * (3 - 2 * t)  # smoothstep

        lat = a.lat + t * (b.lat - a.lat)
        lng = a.lng + t * (b.lng - a.lng)
        return lat, lng

    def speed_at(self, timestamp: float) -> Optional[float]:
        """
        Estimate speed in km/h at the given timestamp by examining the
        local GPS segment. Returns None if the segment has zero duration.
        """
        points = self._points
        if len(points) < 2:
            return None

        # Find bracketing segment (same binary search)
        if timestamp <= points[0].timestamp:
            a, b = points[0], points[1]
        elif timestamp >= points[-1].timestamp:
            a, b = points[-2], points[-1]
        else:
            lo, hi = 0, len(points) - 1
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                if points[mid].timestamp <= timestamp:
                    lo = mid
                else:
                    hi = mid
            a, b = points[lo], points[hi]

        dt = b.timestamp - a.timestamp
        if dt == 0:
            return None

        dist_m = _haversine_m(a.lat, a.lng, b.lat, b.lng)
        speed_ms = dist_m / dt
        return speed_ms * 3.6  # m/s → km/h

    @property
    def start_position(self) -> Tuple[float, float]:
        return self._points[0].lat, self._points[0].lng

    @property
    def end_position(self) -> Tuple[float, float]:
        return self._points[-1].lat, self._points[-1].lng

    @property
    def total_duration(self) -> float:
        return self._points[-1].timestamp

    @property
    def waypoint_count(self) -> int:
        return len(self._points)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in metres between two lat/lng points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Public alias for haversine distance (used by deduplication module)."""
    return _haversine_m(lat1, lng1, lat2, lng2)
