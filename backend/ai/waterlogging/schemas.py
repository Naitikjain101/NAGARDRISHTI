"""
Urban Watch — Schemas for Waterlogging Detection
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class WaterloggingDetection(BaseModel):
    """
    A single frame waterlogging detection instance.
    Includes segmentation mask (polygon points) and area ratio.
    """
    class_id: int = 0
    class_name: str = "waterlogging"
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(
        min_length=4, max_length=4,
        description="[x1, y1, x2, y2] in original image pixel coordinates"
    )
    polygon: List[List[float]] = Field(
        default_factory=list,
        description="List of [x, y] coordinates forming the segmentation mask"
    )
    area_ratio: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Fraction of the bounding box / frame occupied by the mask"
    )

    def bbox_valid(self, frame_width: int, frame_height: int) -> bool:
        x1, y1, x2, y2 = self.bbox
        return (
            0 <= x1 < x2 <= frame_width
            and 0 <= y1 < y2 <= frame_height
        )
