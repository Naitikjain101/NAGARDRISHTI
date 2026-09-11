import pytest
from ai.unified.filters import GeometryFilter
from ai.pothole.schemas import PotholeDetection

def test_geometry_filter_valid():
    filter = GeometryFilter(
        min_area_ratio=0.01,
        max_area_ratio=0.5,
        min_aspect_ratio=0.5,
        max_aspect_ratio=2.0
    )
    
    # 100x100 frame. Area = 10000.
    # Bbox: 10x10 = 100 area (0.01 ratio). Aspect ratio: 1.0.
    det = PotholeDetection(bbox=[0, 0, 10, 10], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert not is_rejected

def test_geometry_filter_too_small():
    filter = GeometryFilter(
        min_area_ratio=0.01,
        max_area_ratio=0.5,
        min_aspect_ratio=0.5,
        max_aspect_ratio=2.0
    )
    # Bbox: 5x5 = 25 area (0.0025 ratio < 0.01)
    det = PotholeDetection(bbox=[0, 0, 5, 5], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert is_rejected
    assert "too_small" in reason

def test_geometry_filter_invalid_aspect_ratio():
    filter = GeometryFilter(
        min_area_ratio=0.01,
        max_area_ratio=0.5,
        min_aspect_ratio=0.5,
        max_aspect_ratio=2.0
    )
    # Bbox: 40x10. Aspect = 4.0 (too wide)
    det = PotholeDetection(bbox=[0, 0, 40, 10], confidence=0.5)
    is_rejected, reason = filter.evaluate(det, 100, 100)
    assert is_rejected
    assert "invalid_aspect_ratio_wide" in reason

    # Bbox: 10x40. Aspect = 0.25 (too tall)
    det2 = PotholeDetection(bbox=[0, 0, 10, 40], confidence=0.5)
    is_rejected, reason = filter.evaluate(det2, 100, 100)
    assert is_rejected
    assert "invalid_aspect_ratio_tall" in reason
