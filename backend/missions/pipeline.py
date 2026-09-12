"""
Urban Watch — Observation → Incident Pipeline

Orchestrates the complete flow for one detection event:
  1. Receive a raw AI detection (type, confidence, bbox, video_timestamp)
  2. Resolve video_timestamp → GPS (lat, lng) via DetectionResolver
  3. Run deduplication (L3 spatial + L4 cross-bus) via DeduplicationPipeline
  4. Update mission session telemetry
  5. Return the pipeline result

This is the single entry point for wiring AI output into the
mission architecture. It is called per-event from routes_unified.py
during or after video processing.

Usage:
    from missions.pipeline import MissionPipeline
    pipeline = MissionPipeline(client, mission_id, bus_id, route_points)
    result = pipeline.process_event(detection_dict)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from supabase import Client

from ai.gis.resolver import DetectionResolver
from missions.deduplication import DeduplicationPipeline
from missions import session as session_manager

logger = logging.getLogger("urban_watch.missions.pipeline")


class MissionPipeline:
    """
    End-to-end pipeline: AI detection → GPS → dedup → incident + observation.

    One pipeline instance per mission run; reused for all events in that mission.
    """

    def __init__(
        self,
        client: Client,
        mission_id: str,
        bus_id: str,
        route_name: str,
        route_points: List[Dict[str, Any]],
        mode: str = "replay",
    ) -> None:
        self.client     = client
        self.mission_id = mission_id
        self.bus_id     = bus_id

        self._resolver  = DetectionResolver(route_points)
        self._dedup     = DeduplicationPipeline(client)

        # Create / resume the in-memory session for telemetry
        self._session = session_manager.create_or_resume_session(
            mission_id=mission_id,
            bus_id=bus_id,
            route_name=route_name,
            mode=mode,
            route_points=route_points,
        )

    def process_event(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process one AI detection event through the full pipeline.

        Parameters
        ----------
        detection : dict
            Required keys:
              incident_type   : str   e.g. "pothole"
              confidence      : float 0-1
              video_timestamp : float seconds into video
            Optional:
              frame_index     : int
              bbox            : list [x1,y1,x2,y2]
              severity        : str (will be computed if missing)

        Returns
        -------
        dict with: action, incident_id, observation_id, observation_count, dedup_status,
                   latitude, longitude, video_timestamp
        """
        # ── Phase D: GPS Resolution ───────────────────────────────────────────
        video_ts = float(detection.get("video_timestamp", 0.0))
        lat, lng = self._resolver.resolve(video_ts)

        enriched = {
            **detection,
            "latitude":        round(lat, 6),
            "longitude":       round(lng, 6),
            "video_timestamp": video_ts,
            "incident_type":   detection.get("incident_type", "unknown"),
        }

        # ── Phase E+F: Deduplication ──────────────────────────────────────────
        result = self._dedup.process(
            detection=enriched,
            mission_id=self.mission_id,
            bus_id=self.bus_id,
        )

        # ── Update session telemetry ──────────────────────────────────────────
        severity = detection.get("severity", "LOW")
        self._session.record_detection(
            incident_type=enriched["incident_type"],
            severity=severity,
            video_timestamp=video_ts,
            lat=lat,
            lng=lng,
        )

        result["latitude"]        = lat
        result["longitude"]       = lng
        result["video_timestamp"] = video_ts

        logger.debug(
            "pipeline: action=%s incident_id=%s type=%s lat=%.5f lng=%.5f conf=%.3f",
            result["action"],
            result["incident_id"],
            enriched["incident_type"],
            lat, lng,
            enriched.get("confidence", 0),
        )

        return result

    def process_batch(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a list of detection events (e.g. after full video processing)."""
        results = []
        for det in detections:
            try:
                r = self.process_event(det)
                results.append(r)
            except Exception as e:
                logger.error(
                    "Pipeline error for detection %s: %s",
                    det.get("incident_type"), e
                )
        return results

    def get_telemetry(self):
        """Return current telemetry snapshot for this mission."""
        return self._session.snapshot()

    @classmethod
    def from_db(
        cls,
        client: Client,
        mission_id: str,
        mode: str = "replay",
    ) -> Optional["MissionPipeline"]:
        """
        Build a MissionPipeline by loading mission data from Supabase.

        Returns None if the mission doesn't exist or has insufficient GPS points.
        """
        from db.mission_repository import MissionRepository
        repo = MissionRepository(client)

        mission = repo.get_mission(mission_id)
        if not mission:
            logger.error("Mission %s not found in DB", mission_id)
            return None

        route_points = repo.get_route_points(mission_id)
        if len(route_points) < 2:
            logger.error(
                "Mission %s has only %d route points — need ≥ 2",
                mission_id, len(route_points),
            )
            return None

        return cls(
            client=client,
            mission_id=mission_id,
            bus_id=mission["bus_id"],
            route_name=mission["route_name"],
            route_points=route_points,
            mode=mode,
        )
