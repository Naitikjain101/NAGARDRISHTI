"""
Phase A Test — Mission Ingest Verification

Run AFTER applying the SQL migration in Supabase:
    python3 tests/test_mission_ingest.py

Verifies:
  1. All 3 demo mission JSONs pass schema validation
  2. Ingestion writes mission rows to demo_missions table
  3. Route points are queryable back from route_points table
  4. Duplicate ingest is idempotent (no extra rows)
  5. Bad metadata raises MissionIngestionError
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from pathlib import Path

DEMO_DIR   = Path(__file__).parent.parent / "demo_videos"
MISSION_DIR = Path(__file__).parent.parent / "demo_missions"

# ── Schema validation (no DB needed) ─────────────────────────────────────────

from missions.schemas import MissionMetadata
from pydantic import ValidationError

MISSION_FILES = list(MISSION_DIR.glob("mission_*.json"))

@pytest.mark.parametrize("json_path", MISSION_FILES, ids=[f.stem for f in MISSION_FILES])
def test_mission_json_validates(json_path):
    """All demo mission JSONs must pass MissionMetadata validation."""
    with open(json_path) as f:
        raw = json.load(f)
    meta = MissionMetadata(**raw)
    assert meta.bus_id
    assert len(meta.gps) >= 2
    assert meta.duration > 0
    gps_timestamps = [p.timestamp for p in meta.gps]
    assert gps_timestamps == sorted(gps_timestamps), "GPS timestamps not ascending"
    assert max(gps_timestamps) <= meta.duration, "GPS timestamp exceeds duration"


def test_missing_bus_id_raises():
    with pytest.raises(ValidationError):
        MissionMetadata(
            bus_id="",
            route_id="R-01",
            route_name="Test Route",
            video_filename="potholes.mp4",
            duration=100,
            gps=[
                {"timestamp": 0,   "lat": 26.9, "lng": 75.8},
                {"timestamp": 100, "lat": 26.91, "lng": 75.81},
            ]
        )


def test_single_gps_point_raises():
    with pytest.raises(ValidationError):
        MissionMetadata(
            bus_id="BUS-999",
            route_id="R-99",
            route_name="Bad Route",
            video_filename="potholes.mp4",
            duration=100,
            gps=[{"timestamp": 0, "lat": 26.9, "lng": 75.8}]
        )


def test_gps_timestamp_exceeds_duration_raises():
    with pytest.raises(ValidationError):
        MissionMetadata(
            bus_id="BUS-999",
            route_id="R-99",
            route_name="Bad Route",
            video_filename="potholes.mp4",
            duration=50,
            gps=[
                {"timestamp": 0,  "lat": 26.9,  "lng": 75.8},
                {"timestamp": 99, "lat": 26.91, "lng": 75.81},  # 99 > 50
            ]
        )


def test_non_ascending_gps_raises():
    with pytest.raises(ValidationError):
        MissionMetadata(
            bus_id="BUS-999",
            route_id="R-99",
            route_name="Bad Route",
            video_filename="potholes.mp4",
            duration=100,
            gps=[
                {"timestamp": 0,  "lat": 26.9,  "lng": 75.8},
                {"timestamp": 60, "lat": 26.91, "lng": 75.81},
                {"timestamp": 30, "lat": 26.92, "lng": 75.82},  # non-ascending
            ]
        )


# ── DB integration tests (require Supabase migration to be applied) ───────────

def _get_client():
    from db.supabase_client import get_supabase
    return get_supabase()

def _get_ingester():
    from missions.ingestion import MissionIngester
    return MissionIngester(_get_client(), demo_dir=DEMO_DIR)


@pytest.mark.integration
def test_ingest_all_three_missions():
    """Ingest all 3 demo missions and verify they are queryable."""
    from db.mission_repository import MissionRepository
    ingester = _get_ingester()
    client = _get_client()
    repo = MissionRepository(client)

    for json_path in MISSION_FILES:
        record = ingester.ingest_from_file(json_path)
        assert record.id, f"No mission ID returned for {json_path.name}"

        # Verify queryable from DB
        fetched = repo.get_mission(record.id)
        assert fetched is not None, f"Mission {record.id} not found in DB"
        assert fetched["bus_id"] == record.bus_id
        assert fetched["route_name"] == record.route_name

        # Verify route points are stored
        points = repo.get_route_points(record.id)
        assert len(points) >= 2, f"Expected ≥2 route points for {record.id}"

        print(f"  ✓ {fetched['bus_id']} — {fetched['route_name']} — {len(points)} GPS points")


@pytest.mark.integration
def test_ingest_is_idempotent():
    """Re-ingesting the same mission must not create duplicate rows."""
    from db.mission_repository import MissionRepository
    ingester = _get_ingester()
    client = _get_client()
    repo = MissionRepository(client)

    json_path = MISSION_FILES[0]

    r1 = ingester.ingest_from_file(json_path)
    r2 = ingester.ingest_from_file(json_path)
    assert r1.id == r2.id, "Re-ingest created a duplicate mission row!"

    missions = repo.get_mission_by_bus(r1.bus_id)
    same_video = [m for m in missions if m["video_filename"] == r1.video_filename]
    assert len(same_video) == 1, f"Expected 1 mission, got {len(same_video)} duplicates"
    print("  ✓ Idempotent ingest confirmed — no duplicate rows")


@pytest.mark.integration
def test_video_file_not_found_raises():
    """Ingesting a mission whose video file doesn't exist must raise."""
    from missions.ingestion import MissionIngestionError
    ingester = _get_ingester()
    with pytest.raises(MissionIngestionError, match="not found"):
        ingester.ingest({
            "bus_id": "BUS-999",
            "route_id": "R-99",
            "route_name": "Ghost Route",
            "video_filename": "nonexistent_video.mp4",
            "duration": 100,
            "gps": [
                {"timestamp": 0,   "lat": 26.9, "lng": 75.8},
                {"timestamp": 100, "lat": 26.91, "lng": 75.81},
            ]
        })


if __name__ == "__main__":
    # Run integration tests directly
    print("Running integration tests (requires Supabase migration)...")
    test_ingest_all_three_missions()
    test_ingest_is_idempotent()
    test_video_file_not_found_raises()
    print("\nAll integration tests passed!")
