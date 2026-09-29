"""
Urban Watch — Mission Ingestion Service

Validates a MissionMetadata JSON, checks the video file exists,
registers the mission in Supabase, and bulk-inserts the GPS route points.

Usage:
    from missions.ingestion import MissionIngester
    ingester = MissionIngester(client, demo_dir=Path("demo_videos"))
    result = ingester.ingest(metadata_dict)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import ValidationError
from supabase import Client

from missions.schemas import MissionMetadata, MissionRecord
from db.mission_repository import MissionRepository

logger = logging.getLogger("urban_watch.missions.ingestion")


class MissionIngestionError(Exception):
    """Raised when mission ingestion fails validation or DB write."""
    pass


class MissionIngester:
    """
    Validates and persists a demo mission.

    Parameters
    ----------
    client : supabase.Client
        Authenticated Supabase service-role client.
    demo_dir : Path
        Directory where demo video files live (e.g. backend/demo_videos/).
    """

    def __init__(self, client: Client, demo_dir: Path) -> None:
        self.client = client
        self.demo_dir = Path(demo_dir)
        self.repo = MissionRepository(client)

    def ingest(self, raw: Dict[str, Any]) -> MissionRecord:
        """
        Ingest a mission from a raw dict (parsed from JSON).

        Steps:
          1. Validate against MissionMetadata schema
          2. Check video file exists in demo_dir
          3. Check for duplicate (same bus_id + video_filename)
          4. Insert demo_mission row
          5. Bulk-insert route_points
          6. Return MissionRecord

        Raises
        ------
        MissionIngestionError
            For any validation, file-not-found, or DB failure.
        """
        # Step 1: Schema validation
        try:
            meta = MissionMetadata(**raw)
        except ValidationError as e:
            raise MissionIngestionError(f"Invalid mission metadata: {e}") from e

        # Step 2: Video file must exist
        video_path = self.demo_dir / meta.video_filename
        if not video_path.exists():
            raise MissionIngestionError(
                f"Video file not found: {video_path}. "
                f"Place the file in {self.demo_dir} before ingesting."
            )

        # Step 3: Duplicate check — same bus + video already registered
        existing = self.repo.get_mission_by_bus(meta.bus_id)
        for m in existing:
            if m.get("video_filename") == meta.video_filename:
                logger.warning(
                    "Mission already exists for bus=%s video=%s (id=%s) — skipping ingest.",
                    meta.bus_id, meta.video_filename, m["id"],
                )
                return MissionRecord(**m)

        # Step 4: Insert mission row
        mission_row = self.repo.create_mission(
            {
                "bus_id":          meta.bus_id,
                "route_id":        meta.route_id,
                "route_name":      meta.route_name,
                "video_filename":  meta.video_filename,
                "duration_seconds": meta.duration,
                "status":          "READY",
                "metadata":        {
                    "gps_point_count": len(meta.gps),
                },
            }
        )
        if not mission_row:
            raise MissionIngestionError("DB insert for demo_mission failed")

        mission_id = mission_row["id"]
        logger.info(
            "Mission registered: id=%s bus=%s route=%s video=%s",
            mission_id, meta.bus_id, meta.route_id, meta.video_filename,
        )

        # Step 5: Bulk-insert GPS route points
        gps_dicts = [{"timestamp": p.timestamp, "lat": p.lat, "lng": p.lng} for p in meta.gps]
        inserted = self.repo.bulk_insert_route_points(mission_id, gps_dicts)
        logger.info(
            "Route points inserted: mission_id=%s count=%d/%d",
            mission_id, inserted, len(gps_dicts),
        )

        return MissionRecord(**mission_row)

    def ingest_from_file(self, json_path: Path) -> MissionRecord:
        """Load a JSON file and ingest the mission."""
        with open(json_path) as f:
            raw = json.load(f)
        return self.ingest(raw)
