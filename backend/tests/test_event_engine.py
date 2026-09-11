import pytest
from ai.unified.events import UnifiedEventEngine
from ai.pothole.schemas import PotholeDetection
from ai.unified.schemas import EventStatus, SeverityLevel

def test_event_engine_filtering():
    # Provide dummy tracker kwargs
    engine = UnifiedEventEngine(
        frame_width=1000, 
        frame_height=1000,
        tracker_kwargs={
            "min_event_frames": 2,
            "frame_gap_tolerance": 5,
            "iou_threshold": 0.20
        }
    )
    
    # 1. Provide a detection that gets rejected by ROI (in the top 35%)
    d_roi = PotholeDetection(bbox=[100, 100, 200, 200], confidence=0.8) # y=100-200, which is < 350
    # 2. Provide a detection that gets rejected by Geometry (too large)
    d_geom = PotholeDetection(bbox=[400, 400, 950, 950], confidence=0.8) # 550x550 = 302500 > 30% of 1M
    # 3. Provide a valid candidate
    d_valid = PotholeDetection(bbox=[500, 500, 550, 550], confidence=0.8) # 50x50 = 2500 area, aspect = 1. y=500-550 (bottom)
    
    active_ids = engine.update(1, 0.1, [d_roi, d_geom, d_valid], [])
    
    assert engine.rejection_stats.total_raw == 3
    assert engine.rejection_stats.rejected_roi == 1
    assert engine.rejection_stats.rejected_geometry == 1
    
    # Send it again to confirm it
    engine.update(2, 0.2, [d_valid], [])
    
    events = engine.finalize()
    assert len(events) == 1
    
    ev = events[0]
    assert ev.status == EventStatus.CONFIRMED
    assert ev.estimated_severity in [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
