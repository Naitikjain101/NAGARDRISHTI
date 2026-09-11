"""
Urban Watch — Pydantic Schemas for Pothole Detection & Analytics
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PotholeDetection(BaseModel):
    """
    A single frame pothole detection.
    Coordinates are in original video/image pixel space.
    """
    class_id: int = 0
    class_name: str = "pothole"
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(
        min_length=4, max_length=4,
        description="[x1, y1, x2, y2] in original image pixel coordinates"
    )

    def bbox_valid(self, frame_width: int, frame_height: int) -> bool:
        x1, y1, x2, y2 = self.bbox
        return (
            0 <= x1 < x2 <= frame_width
            and 0 <= y1 < y2 <= frame_height
        )


class PotholeEvent(BaseModel):
    """
    A tracked physical pothole across consecutive video frames.
    Prevents duplicate reporting of the same pothole.
    """
    event_id: int
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    total_detections: int
    span_frames: int
    stability_score: float = Field(
        ge=0.0, le=1.0,
        description="Fraction of frames in which the pothole was detected over its lifespan"
    )
    max_confidence: float = Field(ge=0.0, le=1.0)
    mean_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    representative_bbox: List[float] = Field(min_length=4, max_length=4)
    is_confirmed: bool = True


class PotholeFrameResult(BaseModel):
    """Detection output for a single video frame."""
    frame_index: int
    timestamp: float
    detections: List[PotholeDetection] = Field(default_factory=list)
    active_event_ids: List[int] = Field(default_factory=list)


class PotholeVideoSummary(BaseModel):
    """Summary of pothole events detected in a video."""
    video_id: str
    total_frames: int
    frames_with_potholes: int
    unique_pothole_events: int
    confirmed_events: int
    transient_blips: int
    events: List[PotholeEvent] = Field(default_factory=list)
    processing_fps: float
    model_name: str
    inference_imgsz: int
    confidence_threshold: float
