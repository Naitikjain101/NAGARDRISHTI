"""
Urban Watch — Phase 3 Pothole Severity Calculator

Calculates image-space severity based on measurable parameters:
- Bounding box area relative to frame
- Maximum detection confidence
- Tracking persistence
"""

from typing import List
from ai.unified.schemas import SeverityLevel
from ai.common.config import POTHOLE_SEVERITY_THRESHOLDS

class SeverityCalculator:
    """
    Assigns a severity label based on image-space area.
    """
    
    @staticmethod
    def calculate(
        representative_bbox: List[float], 
        frame_width: int, 
        frame_height: int
    ) -> SeverityLevel:
        
        if frame_width == 0 or frame_height == 0:
            return SeverityLevel.LOW
            
        x1, y1, x2, y2 = representative_bbox
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)
        
        box_area = w * h
        frame_area = frame_width * frame_height
        
        area_ratio = box_area / frame_area if frame_area > 0 else 0.0
        
        if area_ratio >= POTHOLE_SEVERITY_THRESHOLDS["HIGH_AREA"]:
            return SeverityLevel.CRITICAL
        elif area_ratio >= POTHOLE_SEVERITY_THRESHOLDS["MEDIUM_AREA"]:
            return SeverityLevel.HIGH
        elif area_ratio >= POTHOLE_SEVERITY_THRESHOLDS["LOW_AREA"]:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
