"""
Urban Watch — Detection GPS Resolver

Resolves an AI detection's video_timestamp to a (lat, lng) coordinate
by looking up the mission's GPS timeline and interpolating.

Usage:
    from ai.gis.resolver import DetectionResolver
    resolver = DetectionResolver(route_points)
    lat, lng = resolver.resolve(video_timestamp=124.5)

This module is the bridge between Phase D (GPS resolution) and
Phase E (Observation → Incident pipeline).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Dict, Any

from ai.gis.interpolator import InterpolationEngine, haversine_distance_m

logger = logging.getLogger("urban_watch.ai.gis.resolver")


class DetectionResolver:
    """
    Resolves detections from video space (timestamp) to geographic space (lat/lng).

    Instantiated once per mission run, reused for all detections in that mission.
    """

    def __init__(self, route_points: List[Dict[str, Any]]) -> None:
        """
        Parameters
        ----------
        route_points : list of dicts
            Each dict must have: timestamp (float), lat (float), lng (float)
        """
        self._engine = InterpolationEngine(route_points)

    def resolve(self, video_timestamp: float) -> Tuple[float, float]:
        """
        Map a video timestamp (seconds) to (lat, lng).

        Parameters
        ----------
        video_timestamp : float
            Seconds since video start.

        Returns
        -------
        (lat, lng) tuple
        """
        return self._engine.position_at(video_timestamp)

    def resolve_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a raw detection dict with resolved GPS coordinates.

        Input dict expected keys: video_timestamp, type, confidence, bbox, frame_index
        Returns the same dict with added: latitude, longitude

        Parameters
        ----------
        detection : dict
            Raw detection from UnifiedVideoProcessor output.

        Returns
        -------
        dict with latitude + longitude fields added.
        """
        ts = detection.get("video_timestamp") or detection.get("video_time") or 0.0
        lat, lng = self._engine.position_at(float(ts))
        return {
            **detection,
            "latitude":  round(lat, 6),
            "longitude": round(lng, 6),
        }

    def speed_at(self, video_timestamp: float) -> Optional[float]:
        """Estimated bus speed (km/h) at the given timestamp."""
        return self._engine.speed_at(video_timestamp)

    @property
    def start_position(self) -> Tuple[float, float]:
        return self._engine.start_position

    @property
    def end_position(self) -> Tuple[float, float]:
        return self._engine.end_position


def build_resolver_from_db(mission_id: str, client) -> Optional[DetectionResolver]:
    """
    Convenience factory: loads route points from Supabase and builds a resolver.

    Parameters
    ----------
    mission_id : str
        UUID of the demo_mission.
    client : supabase.Client
        Authenticated Supabase client.

    Returns
    -------
    DetectionResolver or None if route points are missing/insufficient.
    """
    from db.mission_repository import MissionRepository
    repo = MissionRepository(client)
    points = repo.get_route_points(mission_id)
    if len(points) < 2:
        logger.warning(
            "Mission %s has insufficient route points (%d) — cannot resolve GPS",
            mission_id, len(points),
        )
        return None
    return DetectionResolver(points)
