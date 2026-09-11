"""
Urban Watch — Phase 5 Intelligent ROI & Geometric Filters

Filters raw AI detections based on configurable geometric heuristics and Road Surface ROI.
"""

from typing import List, Tuple
import logging
from shapely.geometry import box, Polygon
from ai.pothole.schemas import PotholeDetection

logger = logging.getLogger(__name__)

class RoadROIFilter:
    def __init__(self, roi_polygon: List[List[float]], min_overlap: float):
        """
        roi_polygon: List of normalized [x, y] coordinates defining the ROI
        min_overlap: Minimum percentage of the bounding box that must fall inside the ROI
        """
        self.roi_polygon = Polygon(roi_polygon)
        self.min_overlap = min_overlap
        
    def evaluate(self, detection: PotholeDetection, frame_width: int, frame_height: int) -> Tuple[bool, str]:
        """
        Returns (is_rejected, rejection_reason).
        """
        # Convert bbox [x1, y1, x2, y2] into normalized coords for intersection
        x1, y1, x2, y2 = detection.bbox
        
        nx1, ny1 = x1 / frame_width, y1 / frame_height
        nx2, ny2 = x2 / frame_width, y2 / frame_height
        
        det_box = box(nx1, ny1, nx2, ny2)
        det_area = det_box.area
        
        if det_area == 0:
            return True, "zero_area_bbox"
            
        intersection = self.roi_polygon.intersection(det_box)
        overlap_ratio = intersection.area / det_area
        
        if overlap_ratio < self.min_overlap:
            return True, f"outside_road_roi (overlap={overlap_ratio:.2f})"
            
        return False, ""


class GeometryFilter:
    def __init__(self, min_area_ratio: float, max_area_ratio: float, min_aspect_ratio: float, max_aspect_ratio: float):
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        
    def evaluate(self, detection: PotholeDetection, frame_width: int, frame_height: int) -> Tuple[bool, str]:
        """
        Returns (is_rejected, rejection_reason).
        """
        x1, y1, x2, y2 = detection.bbox
        w = x2 - x1
        h = y2 - y1
        
        if w <= 0 or h <= 0:
            return True, "invalid_geometry"
            
        area = w * h
        frame_area = frame_width * frame_height
        area_ratio = area / frame_area
        
        if area_ratio < self.min_area_ratio:
            return True, f"too_small (ratio={area_ratio:.5f})"
            
        if area_ratio > self.max_area_ratio:
            return True, f"too_large (ratio={area_ratio:.5f})"
            
        aspect_ratio = w / h
        
        if aspect_ratio < self.min_aspect_ratio:
            return True, f"invalid_aspect_ratio_tall (aspect={aspect_ratio:.2f})"
            
        if aspect_ratio > self.max_aspect_ratio:
            return True, f"invalid_aspect_ratio_wide (aspect={aspect_ratio:.2f})"
            
        return False, ""
