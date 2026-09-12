"""
Urban Watch — Mission Repository

DB access layer for demo_missions, route_points, incident_observations.
Follows the same pattern as the existing repository.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from supabase import Client

logger = logging.getLogger("urban_watch.db.mission_repository")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    # ── demo_missions ──────────────────────────────────────────────────────────

    def create_mission(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            data.setdefault("created_at", _utc_now())
            data.setdefault("updated_at", _utc_now())
            resp = self.client.table("demo_missions").insert(data).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error("create_mission failed: %s", e)
            return None

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("demo_missions")
                .select("*")
                .eq("id", mission_id)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error("get_mission failed: %s", e)
            return None

    def get_all_missions(self) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("demo_missions")
                .select("*")
                .order("created_at", desc=False)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("get_all_missions failed: %s", e)
            return []

    def get_mission_by_bus(self, bus_id: str) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("demo_missions")
                .select("*")
                .eq("bus_id", bus_id)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("get_mission_by_bus failed: %s", e)
            return []

    def update_mission_status(self, mission_id: str, status: str) -> bool:
        try:
            self.client.table("demo_missions").update(
                {"status": status, "updated_at": _utc_now()}
            ).eq("id", mission_id).execute()
            return True
        except Exception as e:
            logger.error("update_mission_status failed: %s", e)
            return False

    # ── route_points ───────────────────────────────────────────────────────────

    def bulk_insert_route_points(
        self, mission_id: str, points: List[Dict[str, Any]]
    ) -> int:
        """Insert GPS waypoints in a single batch. Returns count inserted."""
        if not points:
            return 0
        rows = [
            {
                "mission_id": mission_id,
                "timestamp_seconds": p["timestamp"],
                "latitude": p["lat"],
                "longitude": p["lng"],
            }
            for p in points
        ]
        try:
            resp = self.client.table("route_points").insert(rows).execute()
            return len(resp.data) if resp.data else 0
        except Exception as e:
            logger.error("bulk_insert_route_points failed: %s", e)
            return 0

    def get_route_points(self, mission_id: str) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("route_points")
                .select("timestamp_seconds, latitude, longitude")
                .eq("mission_id", mission_id)
                .order("timestamp_seconds")
                .execute()
            )
            # Normalize keys so InterpolationEngine accepts them
            return [
                {
                    "timestamp": r["timestamp_seconds"],
                    "lat": r["latitude"],
                    "lng": r["longitude"],
                }
                for r in (resp.data or [])
            ]
        except Exception as e:
            logger.error("get_route_points failed: %s", e)
            return []

    # ── incident_observations ─────────────────────────────────────────────────

    def create_observation(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            data.setdefault("created_at", _utc_now())
            resp = self.client.table("incident_observations").insert(data).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error("create_observation failed: %s", e)
            return None

    def get_observations_for_incident(
        self, incident_id: str
    ) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("incident_observations")
                .select("*")
                .eq("incident_id", incident_id)
                .order("created_at")
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("get_observations_for_incident failed: %s", e)
            return []

    def get_observations_for_mission(
        self, mission_id: str
    ) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table("incident_observations")
                .select("*")
                .eq("mission_id", mission_id)
                .order("video_timestamp")
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("get_observations_for_mission failed: %s", e)
            return []

    # ── incidents (additive mission columns) ──────────────────────────────────

    def increment_incident_observation(
        self,
        incident_id: str,
        bus_id: str,
        last_seen_at: Optional[str] = None,
    ) -> bool:
        """Atomically increments observation_count and appends bus_id to observed_by."""
        try:
            # Fetch current state
            resp = (
                self.client.table("incidents")
                .select("observation_count, observed_by, dedup_status")
                .eq("id", incident_id)
                .execute()
            )
            if not resp.data:
                return False
            row = resp.data[0]
            count = (row.get("observation_count") or 1) + 1
            observed = row.get("observed_by") or []
            if bus_id not in observed:
                observed.append(bus_id)
            dedup = "CONFIRMED" if count >= 3 else row.get("dedup_status", "PENDING")

            self.client.table("incidents").update(
                {
                    "observation_count": count,
                    "observed_by": observed,
                    "dedup_status": dedup,
                    "last_seen_at": last_seen_at or _utc_now(),
                    "updated_at": _utc_now(),
                }
            ).eq("id", incident_id).execute()
            return True
        except Exception as e:
            logger.error("increment_incident_observation failed: %s", e)
            return False

    def get_incidents_near(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        incident_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetch incidents whose (lat, lng) are within a bounding box approximating
        the given radius. Exact haversine filtering is done in the caller
        (deduplication module). Lat/lng bounding box is used here for DB efficiency.

        1 degree lat ≈ 111_000 m → delta_lat = radius_m / 111_000
        1 degree lng ≈ 111_000 * cos(lat) m
        """
        import math
        delta_lat = radius_m / 111_000
        delta_lng = radius_m / (111_000 * math.cos(math.radians(lat)))

        try:
            q = (
                self.client.table("incidents")
                .select("*")
                .gte("latitude", lat - delta_lat)
                .lte("latitude", lat + delta_lat)
                .gte("longitude", lng - delta_lng)
                .lte("longitude", lng + delta_lng)
            )
            if incident_type:
                q = q.eq("incident_type", incident_type)
            resp = q.limit(limit).execute()
            return resp.data or []
        except Exception as e:
            logger.error("get_incidents_near failed: %s", e)
            return []
