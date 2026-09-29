import pytest
from ai.pothole.tracker import PotholeEventTracker
from ai.pothole.schemas import PotholeDetection

def test_tracker_temporal_gaps():
    # Tracker needs 3 frames minimum to confirm, 
    # but handles gaps of up to 5 frames
    tracker = PotholeEventTracker(
        iou_threshold=0.20,
        frame_gap_tolerance=5,
        min_event_frames=3
    )
    
    # Frame 1: Dets
    d1 = PotholeDetection(bbox=[100, 100, 120, 120], confidence=0.8)
    tracker.update(1, 0.1, [d1])
    
    # Frame 2: Missed (Gap = 1)
    tracker.update(2, 0.2, [])
    
    # Frame 3: Missed (Gap = 2)
    tracker.update(3, 0.3, [])
    
    # Frame 4: Detected again (Gap = 3, which is <= 5)
    # The bbox has shifted slightly but IoU > 0.20
    d2 = PotholeDetection(bbox=[102, 102, 122, 122], confidence=0.85)
    tracker.update(4, 0.4, [d2])
    
    # Frame 5, 6, 7: Missed
    tracker.update(5, 0.5, [])
    tracker.update(6, 0.6, [])
    tracker.update(7, 0.7, [])
    
    # Frame 8: Detected again (Gap = 4)
    d3 = PotholeDetection(bbox=[104, 104, 124, 124], confidence=0.90)
    tracker.update(8, 0.8, [d3])
    
    # Total detections for this object = 3. Should be confirmed.
    
    # Frame 15: Flushing the object (Gap > 5)
    tracker.update(15, 1.5, [])
    
    confirmed = tracker.get_confirmed_events()
    assert len(confirmed) == 1
    ev = confirmed[0]
    
    assert ev.total_detections == 3
    assert ev.span_frames == 8  # Frames 1 through 8
    # max confidence should be 0.90
    assert ev.max_confidence == 0.90
    # mean confidence should be (0.8 + 0.85 + 0.90) / 3 = 0.85
    assert ev.mean_confidence == 0.85
