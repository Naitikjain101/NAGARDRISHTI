"""
Urban Watch — Phase 5 Vehicle-Pothole Interaction Suppressor

Mitigates FP-09 (Moving Vehicle Undercarriage Shadows) by checking
intersections between pothole detections and active vehicle tracks.
"""

from typing import List, Tuple, Optional
from ai.common.config import (
    INTERSECTION_OVER_POTHOLE_AREA,
    INTERSECTION_OVER_VEHICLE_AREA,
    SUPPRESSING_VEHICLE_CLASSES,
)
from ai.common.schemas import TrackResult
from ai.pothole.schemas import PotholeDetection

class VehicleInteractionSuppressor:
    """
    Evaluates whether a pothole detection is actually a vehicle's undercarriage shadow
    by checking bounding box intersections with active vehicles.
    """
    
    def __init__(self) -> None:
        self.min_pothole_overlap = INTERSECTION_OVER_POTHOLE_AREA
        self.min_vehicle_overlap = INTERSECTION_OVER_VEHICLE_AREA
        self.suppressing_classes = SUPPRESSING_VEHICLE_CLASSES

    def evaluate_intersection(
        self, 
        pothole: PotholeDetection, 
        vehicle_tracks: List[TrackResult]
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Evaluate if a pothole is a shadow candidate based on active vehicles.
        
        Returns:
            Tuple: (is_suppressed, reason, overlapping_track_id)
        """
        best_pothole_overlap = 0.0
        best_track_id = None
        best_class = None
        
        for track in vehicle_tracks:
            # Skip classes that don't cast large shadows / cause confusion if configured so
            if track.class_name not in self.suppressing_classes:
                continue
                
            overlap_pothole, overlap_vehicle = self._compute_overlaps(pothole.bbox, track.bbox)
            
            if overlap_pothole > best_pothole_overlap:
                best_pothole_overlap = overlap_pothole
                best_track_id = track.track_id
                best_class = track.class_name
                
            # If BOTH overlaps exceed their minimum thresholds, we suppress
            # ( overlap_vehicle prevents giant truck boxes from suppressing a pothole on the edge
            #   that barely intersects 0.001% of the truck area )
            if overlap_pothole >= self.min_pothole_overlap and overlap_vehicle >= self.min_vehicle_overlap:
                reason = f"suppressed_by_{track.class_name} (pot_overlap={overlap_pothole:.2f}, veh_overlap={overlap_vehicle:.4f})"
                return True, reason, track.track_id
                
        return False, None, None

    @staticmethod
    def _compute_overlaps(pothole_box: List[float], vehicle_box: List[float]) -> Tuple[float, float]:
        """
        Computes intersection area divided by POTHOLE area, AND divided by VEHICLE area.
        Returns: (overlap_ratio_of_pothole, overlap_ratio_of_vehicle)
        """
        xA = max(pothole_box[0], vehicle_box[0])
        yA = max(pothole_box[1], vehicle_box[1])
        xB = min(pothole_box[2], vehicle_box[2])
        yB = min(pothole_box[3], vehicle_box[3])
        
        inter_w = max(0.0, xB - xA)
        inter_h = max(0.0, yB - yA)
        inter_area = inter_w * inter_h
        
        pothole_area = max(0.0, (pothole_box[2] - pothole_box[0]) * (pothole_box[3] - pothole_box[1]))
        vehicle_area = max(0.0, (vehicle_box[2] - vehicle_box[0]) * (vehicle_box[3] - vehicle_box[1]))
        
        overlap_pothole = inter_area / pothole_area if pothole_area > 0 else 0.0
        overlap_vehicle = inter_area / vehicle_area if vehicle_area > 0 else 0.0
        
        return overlap_pothole, overlap_vehicle
