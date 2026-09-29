import pytest
from ai.unified.filters import RoadROIFilter
from ai.pothole.schemas import PotholeDetection

def test_roi_filter_inside():
    # ROI covers the bottom half of a 100x100 frame
    roi = [[0, 0.5], [1, 0.5], [1, 1], [0, 1]]
    filter = RoadROIFilter(roi, min_overlap=0.5)
    
    # Pothole entirely in the bottom half
    det = PotholeDetection(bbox=[10, 60, 20, 70], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert not is_rejected
    
def test_roi_filter_outside():
    roi = [[0, 0.5], [1, 0.5], [1, 1], [0, 1]]
    filter = RoadROIFilter(roi, min_overlap=0.5)
    
    # Pothole entirely in the top half
    det = PotholeDetection(bbox=[10, 10, 20, 20], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert is_rejected
    assert "outside_road_roi" in reason

def test_roi_filter_partial_overlap():
    roi = [[0, 0.5], [1, 0.5], [1, 1], [0, 1]]
    filter = RoadROIFilter(roi, min_overlap=0.6)  # Needs 60% overlap
    
    # Pothole straddles the line (40 to 60)
    # Area = 20x20 = 400.
    # Area inside ROI (50 to 60) = 20x10 = 200.
    # Overlap = 50%
    det = PotholeDetection(bbox=[10, 40, 30, 60], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert is_rejected  # 50% < 60%
    
    # Now set min overlap to 40%
    filter2 = RoadROIFilter(roi, min_overlap=0.4)
    is_rejected, reason = filter2.evaluate(det, 100, 100)
    assert not is_rejected
