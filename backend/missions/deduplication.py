"""
Urban Watch — Deduplication Engine

Implements Levels 3 and 4 of the 4-level deduplication pipeline:

  L1 Frame NMS     — already handled by PotholeDetector._deduplicate_boxes()
  L2 Temporal      — already handled by UnifiedEventEngine + ByteTrack
  L3 Spatial       — this module: haversine radius match against existing incidents
  L4 Cross-bus     — this module: multi-bus observation merging

Design:
  Stateless pure functions + a thin DB-aware wrapper.
  The pure functions are independently unit-testable with no I/O.

Spatial tolerance defaults:
  pothole:      POTHOLE_DEDUP_RADIUS_M  = 25 m
  waterlogging: WATERLOGGING_DEDUP_RADIUS_M = 50 m
  default:      DEFAULT_DEDUP_RADIUS_M  = 30 m
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ai.gis.interpolator import haversine_distance_m

logger = logging.getLogger("urban_watch.missions.deduplication")

# ── Configuration ──────────────────────────────────────────────────────────────

POTHOLE_DEDUP_RADIUS_M      = 25.0
WATERLOGGING_DEDUP_RADIUS_M = 50.0
DEFAULT_DEDUP_RADIUS_M      = 30.0

CONFIRMED_THRESHOLD = 3  # observations → CONFIRMED status


def get_dedup_radius(incident_type: str) -> float:
    """Return the spatial deduplication radius (metres) for a given incident type."""
    return {
        "pothole":      POTHOLE_DEDUP_RADIUS_M,
        "waterlogging": WATERLOGGING_DEDUP_RADIUS_M,
    }.get(incident_type, DEFAULT_DEDUP_RADIUS_M)


# ── Pure spatial functions (no I/O) ───────────────────────────────────────────

def find_matching_incident(
    lat: float,
    lng: float,
    incident_type: str,
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Level 3 — Spatial deduplication.

    Given a new detection's GPS coordinate and a list of existing incident
    candidates (pre-filtered by bounding box in the DB query), find the
    closest existing incident within the type-specific radius.

    Returns the best matching incident dict, or None if no match.

    Parameters
    ----------
    lat, lng : float
        GPS coordinate of the new detection.
    incident_type : str
        e.g. "pothole", "waterlogging"
    candidates : list of dicts
        Existing incident rows from the DB (must have latitude, longitude, incident_type).

    Returns
    -------
    dict or None — the best-matching existing incident.
    """
    radius = get_dedup_radius(incident_type)
    best_match: Optional[Dict[str, Any]] = None
    best_distance = float("inf")

    for inc in candidates:
        if inc.get("incident_type") != incident_type:
            continue
        inc_lat = inc.get("latitude")
        inc_lng = inc.get("longitude")
        if inc_lat is None or inc_lng is None:
            continue

        dist = haversine_distance_m(lat, lng, inc_lat, inc_lng)
        if dist <= radius and dist < best_distance:
            best_distance = dist
            best_match = inc

    if best_match:
        logger.debug(
            "L3 match: type=%s dist=%.1fm incident_id=%s",
            incident_type, best_distance, best_match.get("id"),
        )
    return best_match


def should_confirm_incident(
    observation_count: int,
    observed_by: List[str],
) -> bool:
    """
    Level 4 — Cross-bus consensus.

    An incident is CONFIRMED when it has been independently observed by
    at least CONFIRMED_THRESHOLD different buses OR observation sources.
    """
    return len(set(observed_by)) >= CONFIRMED_THRESHOLD or observation_count >= CONFIRMED_THRESHOLD


def compute_merged_confidence(
    existing_confidence: float,
    new_confidence: float,
    observation_count: int,
) -> float:
    """
    Weighted average of existing and new confidence.
    More observations → existing confidence carries more weight.
    """
    weight_existing = min(observation_count - 1, 10) / 10.0  # caps at 1.0 after 10 obs
    weight_new = 1.0 - weight_existing
    merged = weight_existing * existing_confidence + weight_new * new_confidence
    return round(merged, 4)


def compute_severity(incident_type: str, confidence: float, observation_count: int) -> str:
    """
    Derive severity from confidence + observation count.

    Rules (illustrative — tune to your real data):
      HIGH / CRITICAL for high-confidence repeated observations
      LOW for single low-confidence sightings
    """
    score = confidence * min(observation_count, 5) / 5.0  # normalised 0-1

    if score >= 0.8:
        return "CRITICAL"
    elif score >= 0.6:
        return "HIGH"
    elif score >= 0.35:
        return "MODERATE"
    else:
        return "LOW"


# ── DB-aware pipeline step ────────────────────────────────────────────────────

class DeduplicationPipeline:
    """
    Orchestrates L3+L4 deduplication for one incoming detection.

    Usage:
        pipeline = DeduplicationPipeline(client)
        result = pipeline.process(detection, mission_id, bus_id)
    """

    def __init__(self, client) -> None:
        self.client = client
        from db.mission_repository import MissionRepository
        self.repo = MissionRepository(client)

    def process(
        self,
        detection: Dict[str, Any],
        mission_id: Optional[str],
        bus_id: str,
    ) -> Dict[str, Any]:
        """
        Process one GPS-resolved detection through L3+L4 deduplication.

        Parameters
        ----------
        detection : dict
            Must have: incident_type, latitude, longitude, confidence,
                       video_timestamp, frame_index, bbox (optional)
        mission_id : str or None
            UUID of the source demo_mission.
        bus_id : str
            e.g. "BUS-104"

        Returns
        -------
        dict with keys:
            action          : "created" | "merged"
            incident_id     : str
            observation_id  : str
            observation_count : int
            dedup_status    : str
        """
        incident_type = detection["incident_type"]
        lat           = detection["latitude"]
        lng           = detection["longitude"]
        confidence    = detection.get("confidence", 0.0)
        video_ts      = detection.get("video_timestamp", 0.0)
        frame_index   = detection.get("frame_index")
        bbox          = detection.get("bbox")

        now = datetime.now(timezone.utc).isoformat()

        # ── L3: Spatial match ─────────────────────────────────────────────────
        candidates = self.repo.get_incidents_near(
            lat=lat, lng=lng,
            radius_m=get_dedup_radius(incident_type) * 1.5,  # slightly wider for DB query
            incident_type=incident_type,
        )
        existing = find_matching_incident(lat, lng, incident_type, candidates)

        if existing:
            # ── Merge into existing incident ──────────────────────────────────
            incident_id    = existing["id"]
            obs_count      = (existing.get("observation_count") or 1) + 1
            observed_by    = list(existing.get("observed_by") or [])
            if bus_id not in observed_by:
                observed_by.append(bus_id)

            merged_conf    = compute_merged_confidence(
                existing.get("confidence", confidence), confidence, obs_count
            )
            new_severity   = compute_severity(incident_type, merged_conf, obs_count)
            new_dedup      = "CONFIRMED" if should_confirm_incident(obs_count, observed_by) else "PENDING"

            # Update incident
            self.client.table("incidents").update({
                "observation_count": obs_count,
                "observed_by":       observed_by,
                "confidence":        merged_conf,
                "severity":          new_severity,
                "dedup_status":      new_dedup,
                "last_seen_at":      now,
                "updated_at":        now,
            }).eq("id", incident_id).execute()

            action = "merged"
            obs_count_final = obs_count
            dedup_status    = new_dedup

            logger.info(
                "L3 merge: incident_id=%s type=%s obs=%d bus=%s dedup=%s",
                incident_id, incident_type, obs_count, bus_id, new_dedup,
            )

        else:
            # ── Create new incident ───────────────────────────────────────────
            initial_severity = compute_severity(incident_type, confidence, 1)
            new_inc = {
                "incident_type":    incident_type,
                "latitude":         lat,
                "longitude":        lng,
                "confidence":       confidence,
                "severity":         initial_severity,
                "status":           "OPEN",
                "observation_count": 1,
                "observed_by":      [bus_id],
                "dedup_status":     "PENDING",
                "source_mission_id": mission_id,
                "first_seen_at":    now,
                "last_seen_at":     now,
                "timestamp":        now,
                "frame_index":      frame_index,
                "bbox":             bbox,
            }
            resp = self.client.table("incidents").insert(new_inc).execute()
            if not resp.data:
                raise RuntimeError("Failed to insert new incident into DB")
            incident_id     = resp.data[0]["id"]
            action          = "created"
            obs_count_final = 1
            dedup_status    = "PENDING"

            logger.info(
                "L3 new: incident_id=%s type=%s lat=%.5f lng=%.5f conf=%.3f bus=%s",
                incident_id, incident_type, lat, lng, confidence, bus_id,
            )

        # ── Create observation record (always) ────────────────────────────────
        obs_resp = self.repo.create_observation({
            "incident_id":     incident_id,
            "mission_id":      mission_id,
            "bus_id":          bus_id,
            "video_timestamp": video_ts,
            "latitude":        lat,
            "longitude":       lng,
            "confidence":      confidence,
            "bbox":            bbox,
            "frame_index":     frame_index,
        })
        observation_id = obs_resp["id"] if obs_resp else None

        return {
            "action":            action,
            "incident_id":       incident_id,
            "observation_id":    observation_id,
            "observation_count": obs_count_final,
            "dedup_status":      dedup_status,
        }
