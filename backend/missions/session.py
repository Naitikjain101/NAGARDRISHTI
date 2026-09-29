"""
Urban Watch — Mission Session Manager

Manages the live state of running missions (both REPLAY and LIVE modes).
The frontend polls GET /api/missions/{id}/telemetry to get this state.

Design:
  - In-memory session store (no DB writes per-tick)
  - Telemetry is derived live from playback position + GPS interpolation
  - Thread-safe for concurrent sessions (multiple buses running simultaneously)
  - Sessions survive across polling gaps (no timeout-based cleanup during a run)
"""

from __future__ import annotations

import threading
import time
import logging
from typing import Dict, Optional, Any

from ai.gis.interpolator import InterpolationEngine
from missions.schemas import TelemetrySnapshot

logger = logging.getLogger("urban_watch.missions.session")

# Global session registry: mission_id → MissionSession
_sessions: Dict[str, "MissionSession"] = {}
_sessions_lock = threading.Lock()


def get_session(mission_id: str) -> Optional["MissionSession"]:
    with _sessions_lock:
        return _sessions.get(mission_id)


def create_or_resume_session(
    mission_id: str,
    bus_id: str,
    route_name: str,
    mode: str,          # "replay" | "live"
    route_points: list, # raw dicts from DB: [{timestamp, lat, lng}, ...]
) -> "MissionSession":
    with _sessions_lock:
        if mission_id in _sessions:
            logger.info("Resuming existing session for mission=%s", mission_id)
            return _sessions[mission_id]
        session = MissionSession(
            mission_id=mission_id,
            bus_id=bus_id,
            route_name=route_name,
            mode=mode,
            route_points=route_points,
        )
        _sessions[mission_id] = session
        logger.info(
            "Created session mission=%s bus=%s mode=%s",
            mission_id, bus_id, mode,
        )
        return session


def destroy_session(mission_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(mission_id, None)
        logger.info("Destroyed session mission=%s", mission_id)


def list_active_sessions() -> list:
    """Return telemetry snapshots for all active sessions."""
    with _sessions_lock:
        return [s.snapshot() for s in _sessions.values()]


class MissionSession:
    """
    Stateful object for one running mission.

    Replay mode:
      The caller advances `current_timestamp` by calling tick(elapsed_seconds).
      Typically the frontend's video player controls playback speed.

    Live mode:
      `current_timestamp` is set to real wall-clock offset since session start.
    """

    def __init__(
        self,
        mission_id: str,
        bus_id: str,
        route_name: str,
        mode: str,
        route_points: list,
    ) -> None:
        self.mission_id  = mission_id
        self.bus_id      = bus_id
        self.route_name  = route_name
        self.mode        = mode  # "replay" | "live"

        self._engine = InterpolationEngine(route_points)
        self._lock   = threading.Lock()

        self._current_timestamp: float = 0.0
        self._started_at: float = time.monotonic()

        # Running counts (updated by the AI pipeline as detections arrive)
        self._pothole_count:      int = 0
        self._waterlogging_count: int = 0
        self._vehicle_count:      int = 0

        # Most recent event
        self._last_event: Optional[Dict[str, Any]] = None

        # AI status
        self._ai_status: str = "idle"

    # ── Playback control ───────────────────────────────────────────────────────

    def seek(self, timestamp: float) -> None:
        """Jump to a specific position in the video (seconds)."""
        with self._lock:
            self._current_timestamp = max(0.0, timestamp)

    def tick(self, elapsed_seconds: float) -> None:
        """
        Advance playback by elapsed_seconds.
        For REPLAY mode — called by the video player sync mechanism.
        """
        with self._lock:
            self._current_timestamp += elapsed_seconds

    def sync_to_live(self) -> None:
        """LIVE mode: set current_timestamp to wall-clock offset since session start."""
        with self._lock:
            self._current_timestamp = time.monotonic() - self._started_at

    # ── AI pipeline integration ────────────────────────────────────────────────

    def record_detection(
        self,
        incident_type: str,
        severity: str,
        video_timestamp: float,
        lat: float,
        lng: float,
    ) -> None:
        """Called by the AI pipeline whenever a new incident is confirmed."""
        with self._lock:
            if incident_type == "pothole":
                self._pothole_count += 1
            elif incident_type == "waterlogging":
                self._waterlogging_count += 1
            elif incident_type in ("vehicle", "car", "bus", "truck"):
                self._vehicle_count += 1

            self._last_event = {
                "type":      incident_type,
                "severity":  severity,
                "timestamp": video_timestamp,
                "lat":       lat,
                "lng":       lng,
            }

    def set_ai_status(self, status: str) -> None:
        """Status: 'detecting' | 'processing' | 'idle'"""
        with self._lock:
            self._ai_status = status

    # ── Telemetry snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> TelemetrySnapshot:
        """Thread-safe telemetry snapshot for frontend polling."""
        with self._lock:
            ts = self._current_timestamp
            lat, lng = self._engine.position_at(ts)
            speed = self._engine.speed_at(ts)
            last = self._last_event

        return TelemetrySnapshot(
            mission_id=self.mission_id,
            bus_id=self.bus_id,
            route_name=self.route_name,
            mode=self.mode,
            current_timestamp=round(ts, 2),
            current_lat=round(lat, 6),
            current_lng=round(lng, 6),
            speed_kmh=round(speed, 1) if speed is not None else None,
            ai_status=self._ai_status,
            pothole_count=self._pothole_count,
            waterlogging_count=self._waterlogging_count,
            vehicle_count=self._vehicle_count,
            last_event_type=last["type"]      if last else None,
            last_event_severity=last["severity"]  if last else None,
            last_event_timestamp=last["timestamp"] if last else None,
            last_event_lat=last["lat"]        if last else None,
            last_event_lng=last["lng"]        if last else None,
        )

    @property
    def current_position(self):
        """(lat, lng) at current playback position."""
        with self._lock:
            return self._engine.position_at(self._current_timestamp)
