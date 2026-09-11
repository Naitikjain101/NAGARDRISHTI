"""
Unit tests for Urban Watch Vehicle Precision Upgrade:
- Smart Geometric Duplicate Suppression
- Temporal Class Stabilization
- Track Identity & Precision
"""

import pytest
import numpy as np
import torch
from ai.common.schemas import DetectionResult, TrackResult
from ai.detection.vehicle_suppression import VehicleDuplicateSuppressor
from ai.tracking.tracker import ByteTracker, stabilize_class


class DummyModel:
    """Mock model for unit tests."""
    def __init__(self):
        self.names = {
            0: "person",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
        }
        self.device = "cpu"


# ---------------------------------------------------------------------------
# Test A: Same-class duplicate suppression
# ---------------------------------------------------------------------------
def test_same_class_duplicate_suppression():
    suppressor = VehicleDuplicateSuppressor(same_class_iou=0.75)
    
    # Two almost identical car boxes
    b1 = [100.0, 100.0, 300.0, 300.0]
    b2 = [105.0, 102.0, 302.0, 298.0]
    
    det1 = DetectionResult(class_id=2, class_name="car", confidence=0.85, bbox=b1)
    det2 = DetectionResult(class_id=2, class_name="car", confidence=0.60, bbox=b2)
    
    filtered, diag = suppressor.suppress_detections([det1, det2])
    
    assert len(filtered) == 1
    assert filtered[0].confidence == 0.85
    assert filtered[0].class_name == "car"
    assert diag.same_class_suppressed == 1
    assert diag.cross_class_suppressed == 0


# ---------------------------------------------------------------------------
# Test B: Cross-class nested duplicate (Car + Truck)
# ---------------------------------------------------------------------------
def test_cross_class_nested_duplicate_car_truck():
    suppressor = VehicleDuplicateSuppressor(cross_class_iou=0.65, cross_class_iomin=0.80)
    
    # Larger truck box enclosing smaller car box
    b_truck = [100.0, 100.0, 400.0, 400.0]
    b_car = [120.0, 120.0, 380.0, 380.0]
    
    det_truck = DetectionResult(class_id=7, class_name="truck", confidence=0.78, bbox=b_truck)
    det_car = DetectionResult(class_id=2, class_name="car", confidence=0.45, bbox=b_car)
    
    filtered, diag = suppressor.suppress_detections([det_truck, det_car])
    
    assert len(filtered) == 1
    assert filtered[0].class_name == "truck"
    assert filtered[0].confidence == 0.78
    assert diag.cross_class_suppressed == 1


# ---------------------------------------------------------------------------
# Test C: Motorcycle + Bicycle duplicate
# ---------------------------------------------------------------------------
def test_cross_class_motorcycle_bicycle_duplicate():
    suppressor = VehicleDuplicateSuppressor(cross_class_iou=0.65)
    
    # Heavily overlapping bike / motorcycle boxes (IoU ~ 0.85)
    b_moto = [500.0, 300.0, 600.0, 500.0]
    b_bike = [505.0, 298.0, 595.0, 502.0]
    
    det_moto = DetectionResult(class_id=3, class_name="motorcycle", confidence=0.82, bbox=b_moto)
    det_bike = DetectionResult(class_id=1, class_name="bicycle", confidence=0.55, bbox=b_bike)
    
    filtered, diag = suppressor.suppress_detections([det_moto, det_bike])
    
    assert len(filtered) == 1
    assert filtered[0].class_name == "motorcycle"
    assert filtered[0].confidence == 0.82
    assert diag.cross_class_suppressed == 1


# ---------------------------------------------------------------------------
# Test D: Adjacent motorcycles (Keep both)
# ---------------------------------------------------------------------------
def test_adjacent_motorcycles_preserved():
    suppressor = VehicleDuplicateSuppressor(same_class_iou=0.75)
    
    # Two motorcycles side-by-side with slight overlap (IoU ~ 0.25)
    b_moto1 = [100.0, 200.0, 180.0, 400.0]
    b_moto2 = [160.0, 200.0, 240.0, 400.0]
    
    det1 = DetectionResult(class_id=3, class_name="motorcycle", confidence=0.75, bbox=b_moto1)
    det2 = DetectionResult(class_id=3, class_name="motorcycle", confidence=0.70, bbox=b_moto2)
    
    filtered, diag = suppressor.suppress_detections([det1, det2])
    
    assert len(filtered) == 2
    assert diag.same_class_suppressed == 0
    assert diag.cross_class_suppressed == 0


# ---------------------------------------------------------------------------
# Test E: Adjacent Car + Motorcycle (Keep both)
# ---------------------------------------------------------------------------
def test_adjacent_car_and_motorcycle_preserved():
    suppressor = VehicleDuplicateSuppressor(cross_class_iou=0.65, cross_class_iomin=0.80)
    
    # Car in lane with motorcycle riding in adjacent lane (moderate overlap, distinct centers)
    b_car = [200.0, 200.0, 500.0, 600.0]
    b_moto = [450.0, 300.0, 550.0, 550.0]
    
    det_car = DetectionResult(class_id=2, class_name="car", confidence=0.88, bbox=b_car)
    det_moto = DetectionResult(class_id=3, class_name="motorcycle", confidence=0.72, bbox=b_moto)
    
    filtered, diag = suppressor.suppress_detections([det_car, det_moto])
    
    assert len(filtered) == 2
    assert diag.cross_class_suppressed == 0


# ---------------------------------------------------------------------------
# Test F: Person + Motorcycle (Protected pair, keep both)
# ---------------------------------------------------------------------------
def test_person_plus_motorcycle_never_suppressed():
    suppressor = VehicleDuplicateSuppressor()
    
    # Rider box heavily overlapping with motorcycle box
    b_rider = [100.0, 100.0, 180.0, 280.0]
    b_moto = [90.0, 150.0, 190.0, 320.0]
    
    det_person = DetectionResult(class_id=0, class_name="person", confidence=0.65, bbox=b_rider)
    det_moto = DetectionResult(class_id=3, class_name="motorcycle", confidence=0.85, bbox=b_moto)
    
    filtered, diag = suppressor.suppress_detections([det_person, det_moto])
    
    assert len(filtered) == 2
    assert diag.same_class_suppressed == 0
    assert diag.cross_class_suppressed == 0


# ---------------------------------------------------------------------------
# Test G: Temporal class flicker stabilization
# ---------------------------------------------------------------------------
def test_temporal_class_flicker_stabilization():
    # Sequence: car -> truck -> car -> truck -> car (majority car)
    history = [
        ("car", 2, 0.80),
        ("truck", 7, 0.45),
        ("car", 2, 0.82),
        ("truck", 7, 0.50),
        ("car", 2, 0.79),
    ]
    
    stab_name, stab_id = stabilize_class(history)
    assert stab_name == "car"
    assert stab_id == 2


# ---------------------------------------------------------------------------
# Test H: Track Identity (Duplicate detections do not create 2 tracks)
# ---------------------------------------------------------------------------
def test_track_identity_suppression_prevents_duplicate_tracks():
    model = DummyModel()
    tracker = ByteTracker(model=model, device="cpu")
    
    # Filter indices with duplicate boxes
    b1 = [100.0, 100.0, 300.0, 300.0]
    b2 = [104.0, 102.0, 302.0, 298.0]
    
    boxes = np.array([b1, b2])
    classes = np.array([2, 7]) # car vs truck duplicate
    confs = np.array([0.90, 0.40])
    
    keep, diag = tracker._suppressor.filter_indices(boxes, classes, confs, model.names)
    
    assert len(keep) == 1
    assert keep[0] == 0  # Only higher-confidence car is retained
    assert diag.cross_class_suppressed == 1


# ---------------------------------------------------------------------------
# Test I: Empty Detections
# ---------------------------------------------------------------------------
def test_empty_detections_does_not_crash():
    suppressor = VehicleDuplicateSuppressor()
    filtered, diag = suppressor.suppress_detections([])
    assert filtered == []
    assert diag.raw_detections == 0
    assert diag.filtered_detections == 0

    stab_name, stab_id = stabilize_class([])
    assert stab_name == "unknown"
    assert stab_id == -1


# ---------------------------------------------------------------------------
# Test J: Single Detection Passes Unchanged
# ---------------------------------------------------------------------------
def test_single_detection_passes_unchanged():
    suppressor = VehicleDuplicateSuppressor()
    det = DetectionResult(class_id=2, class_name="car", confidence=0.91, bbox=[10.0, 20.0, 100.0, 120.0])
    
    filtered, diag = suppressor.suppress_detections([det])
    assert len(filtered) == 1
    assert filtered[0].class_name == "car"
    assert filtered[0].confidence == 0.91
    assert filtered[0].bbox == [10.0, 20.0, 100.0, 120.0]
    assert diag.raw_detections == 1
    assert diag.filtered_detections == 1
    assert diag.same_class_suppressed == 0
    assert diag.cross_class_suppressed == 0
