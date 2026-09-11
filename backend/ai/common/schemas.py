"""
Urban Watch — Pydantic Result Schemas

All data structures that cross component boundaries use these schemas.
This ensures type safety and clean JSON serialization.

Python 3.9 compatible: uses Optional[T] and List[T] instead of T | None / list[T].
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DensityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Backward-compat alias — remove after all callsites migrated
    PENDING = "queued"
    COMPLETE = "completed"


# ---------------------------------------------------------------------------
# Video Metadata
# ---------------------------------------------------------------------------

class VideoMetadata(BaseModel):
    """Metadata extracted from a video file by VideoReader."""

    video_id: str
    filename: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float
    codec: Optional[str] = None
    file_size_bytes: Optional[int] = None

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Detection (single object in a single frame, no tracking)
# ---------------------------------------------------------------------------

class DetectionResult(BaseModel):
    """
    A single object detection from the detector.

    bbox is in ORIGINAL VIDEO PIXEL COORDINATES.
    Confidence comes directly from model inference — never fabricated.
    """

    class_id: int
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(
        min_length=4, max_length=4,
        description="[x1, y1, x2, y2] in original video pixel coordinates"
    )

    model_config = {"frozen": True}

    def bbox_valid(self, frame_width: int, frame_height: int) -> bool:
        """Check that bbox is within frame bounds."""
        x1, y1, x2, y2 = self.bbox
        return (
            0 <= x1 < x2 <= frame_width
            and 0 <= y1 < y2 <= frame_height
        )


# ---------------------------------------------------------------------------
# Track (persistent object across frames, with track ID)
# ---------------------------------------------------------------------------

class TrackResult(BaseModel):
    """
    A tracked object with persistent identity across frames.

    Raw detections and tracked objects are SEPARATE CONCEPTS.
    A detection without a track_id is valid and is NOT discarded.
    """

    track_id: int
    class_id: int
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(
        min_length=4, max_length=4,
        description="[x1, y1, x2, y2] in original video pixel coordinates"
    )
    first_seen_timestamp: float = Field(
        description="Video timestamp (seconds) when track was first seen"
    )
    last_seen_timestamp: float = Field(
        description="Video timestamp (seconds) when track was last seen"
    )
    frames_seen: int = Field(ge=1, description="Number of frames this track appeared in")
    raw_class: Optional[str] = Field(
        default=None, description="Raw detected class name before temporal stabilization"
    )
    stabilized_class: Optional[str] = Field(
        default=None, description="Temporally stabilized class name"
    )
    class_history: Optional[List[str]] = Field(
        default=None, description="Rolling history of recent classifications"
    )
    track_age: Optional[int] = Field(
        default=None, description="Total elapsed frames since track initialization"
    )
    detection_count: Optional[int] = Field(
        default=None, description="Total detection updates received for this track"
    )


# ---------------------------------------------------------------------------
# Frame Result
# ---------------------------------------------------------------------------

class FrameResult(BaseModel):
    """Complete AI result for a single video frame."""

    frame_index: int
    timestamp: float = Field(description="Video timestamp in seconds")
    detections: List[DetectionResult] = Field(default_factory=list)
    tracks: List[TrackResult] = Field(default_factory=list)
    unique_vehicle_count_in_frame: int = Field(
        default=0,
        description="Unique vehicle track IDs active in this frame"
    )


# ---------------------------------------------------------------------------
# Traffic Analytics
# ---------------------------------------------------------------------------

class VehicleCountSummary(BaseModel):
    """Total unique vehicle counts across the entire video."""

    total_unique_vehicles: int
    by_class: Dict[str, int] = Field(
        description="Count of unique track IDs per vehicle class"
    )


class DensityWindow(BaseModel):
    """Traffic density for a 5-second rolling window."""

    window_start: float
    window_end: float
    unique_vehicle_count: int
    density_level: DensityLevel
    note: str = Field(
        default=(
            "Prototype traffic-density classification based on tracked "
            "vehicle counts. NOT calibrated traffic engineering data."
        )
    )


# ---------------------------------------------------------------------------
# Processing Configuration (stored with results for reproducibility)
# ---------------------------------------------------------------------------

class ProcessingConfig(BaseModel):
    """Records the exact configuration used during AI processing."""

    device: str
    model_name: str
    model_family: Optional[str] = None
    imgsz: int
    confidence_threshold: float
    iou_threshold: float
    frame_interval: int
    batch_size: int
    ultralytics_version: Optional[str] = None
    torch_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-Level Processing Result
# ---------------------------------------------------------------------------

class ProcessingResult(BaseModel):
    """
    Complete AI processing result for a video.

    This is the schema of the JSON file saved to backend/results/{video_id}.json
    """

    video: VideoMetadata
    processing: ProcessingConfig
    status: ProcessingStatus
    error: Optional[str] = None
    frames: List[FrameResult] = Field(default_factory=list)
    vehicle_counts: Optional[VehicleCountSummary] = None
    density_windows: List[DensityWindow] = Field(default_factory=list)
    timing: Dict[str, Any] = Field(
        default_factory=dict,
        description="Timing breakdown in milliseconds"
    )


# ---------------------------------------------------------------------------
# Model Inspection Result
# ---------------------------------------------------------------------------

class ModelInspectionResult(BaseModel):
    """Result of inspecting a model candidate."""

    model_name: str
    pt_file: str
    source_url: Optional[str] = None
    license: Optional[str] = None
    task: Optional[str] = None
    classes: Dict[int, str] = Field(default_factory=dict)
    num_classes: int = 0
    num_parameters: Optional[int] = None
    model_size_mb: Optional[float] = None
    load_time_ms: Optional[float] = None
    required_classes_present: bool = False
    missing_classes: List[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    accepted: bool = False
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# API Response Schemas
# ---------------------------------------------------------------------------

class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    metadata: VideoMetadata


class AIStatusResponse(BaseModel):
    video_id: str
    status: ProcessingStatus
    progress_frames: int = 0
    total_frames: int = 0
    processing_fps: Optional[float] = None
    current_vehicles: int = 0
    current_potholes: int = 0
    current_helmets: int = 0
    current_no_helmets: int = 0
    error: Optional[str] = None


class DeviceResponse(BaseModel):
    device: str
    device_name: Optional[str]
    cuda_available: bool
    mps_available: bool
    torch_version: str
