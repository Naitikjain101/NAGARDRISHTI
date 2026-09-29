"""
Urban Watch — Isolated Pothole Lab Processor

This processor is built exclusively for the /pothole-lab debug route.
It runs the YOLO26m model on videos and returns RAW DETECTIONS and optional
TRACKING data without ANY of the production PotholeValidator suppression logic.

DO NOT import this into production pipelines.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

import numpy as np

from ai.pothole.detector import PotholeDetector, PotholeDetectorConfig
from ai.pothole.tracker import PotholeEventTracker
from video.reader import read_video_info, iter_frames

logger = logging.getLogger(__name__)


class PotholeLabProcessor:
    def __init__(self, model_path: str = "models/pothole/best.pt", confidence: float = 0.10):
        """
        Initialize the isolated lab processor.
        We set the default confidence very low (0.10) so the frontend slider can filter it up.
        """
        self.model_path = model_path
        self.confidence = confidence

        # Initialize detector
        config = PotholeDetectorConfig(
            model_path=self.model_path,
            confidence_threshold=self.confidence,
        )
        self.detector = PotholeDetector(config)

    def process(self, video_path: str, use_tracking: bool = True) -> Dict[str, Any]:
        """
        Process the video and return all raw frames and track summaries.
        """
        logger.info(f"[POTHOLE LAB] Processing video: {video_path}")
        
        # We explicitly initialize the detector here if not loaded
        if not self.detector._is_loaded:
            self.detector.load()

        info = read_video_info(video_path)
        
        tracker = None
        if use_tracking:
            tracker = PotholeEventTracker()

        frames_data = []
        
        for frame_index, timestamp, frame in iter_frames(video_path):
            detections, _ = self.detector.detect(frame, frame_index, timestamp)
            
            raw_dets = []
            for det in detections:
                raw_dets.append({
                    "bbox": det.bbox,
                    "confidence": det.confidence,
                    "class_name": det.class_name
                })
                
            frame_result = {
                "frame_index": frame_index,
                "timestamp": timestamp,
                "pothole_detections": raw_dets,
                "active_pothole_event_ids": []
            }
            
            if use_tracking and tracker is not None:
                # Update tracker
                active_ids = tracker.update(frame_index, timestamp, detections)
                frame_result["active_pothole_event_ids"] = active_ids
                
            frames_data.append(frame_result)
            
        # Collect track summaries if tracking was enabled
        track_summaries = []
        if use_tracking and tracker is not None:
            all_events = tracker.finalize()
            for event in all_events:
                track_summaries.append({
                    "event_id": event.event_id,
                    "first_frame": event.first_seen_frame,
                    "last_frame": event.last_seen_frame,
                    "span_frames": event.span_frames,
                    "total_detections": event.total_detections,
                    "max_confidence": event.max_confidence,
                    "is_confirmed": event.is_confirmed
                })
                
        return {
            "metadata": {
                "video_path": info.path,
                "width": info.width,
                "height": info.height,
                "fps": info.fps,
                "frame_count": info.frame_count,
                "model_path": self.model_path,
                "base_confidence": self.confidence,
                "tracking_enabled": use_tracking
            },
            "frames": frames_data,
            "tracks": track_summaries
        }
