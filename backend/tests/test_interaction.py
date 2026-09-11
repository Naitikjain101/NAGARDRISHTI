import pytest
from ai.unified.interaction import VehicleInteractionSuppressor
from ai.pothole.schemas import PotholeDetection
from ai.common.schemas import TrackResult

def test_vehicle_suppression():
    suppressor = VehicleInteractionSuppressor()
    suppressor.min_pothole_overlap = 0.50
    suppressor.min_vehicle_overlap = 0.01
    
    # 1. Shadow scenario: pothole box completely inside vehicle box, vehicle is large enough
    det = PotholeDetection(bbox=[100, 100, 120, 120], confidence=0.8)  # 20x20 = 400 area
    veh = TrackResult(
        track_id=1, 
        class_id=2, 
        class_name="car", 
        bbox=[80, 80, 200, 200],  # 120x120 = 14400 area
        confidence=0.9,
        first_seen_timestamp=0.0,
        last_seen_timestamp=0.0,
        frames_seen=1
    )
    
    # Pothole area inside vehicle = 400. 
    # Overlap/Pothole = 1.0 (>= 0.5)
    # Overlap/Vehicle = 400/14400 = 0.027 (>= 0.01)
    is_suppressed, reason, track_id = suppressor.evaluate_intersection(det, [veh])
    assert is_suppressed
    assert track_id == 1
    assert "suppressed_by_car" in reason
    
    # 2. Giant truck catching a tiny edge pothole (overlap_vehicle < 0.01)
    det2 = PotholeDetection(bbox=[10, 10, 20, 20], confidence=0.8) # 100 area
    veh_truck = TrackResult(
        track_id=2, 
        class_id=7, 
        class_name="truck", 
        bbox=[5, 5, 1000, 1000],  # 995x995 ~ 1,000,000 area
        confidence=0.9,
        first_seen_timestamp=0.0,
        last_seen_timestamp=0.0,
        frames_seen=1
    )
    
    # Pothole area inside truck = 100
    # Overlap/Pothole = 1.0 (>= 0.5)
    # Overlap/Vehicle = 100 / 990025 = 0.0001 (< 0.01)
    is_suppressed, reason, track_id = suppressor.evaluate_intersection(det2, [veh_truck])
    assert not is_suppressed  # Should not be suppressed because the vehicle overlap ratio is too low
