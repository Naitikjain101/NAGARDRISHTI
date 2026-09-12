"""
Urban Watch — Phase 3 Unified Video Processor

End-to-End Pipeline fusing:
- YOLOv8n (Vehicles) + ByteTrack + Density
- YOLO26n (Potholes) + Interaction + ROI + Unified Event Tracker
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import torch
from ultralytics import YOLO

from ai.common.config import (
    PRODUCTION_MODEL,
    INFERENCE_IMGSZ,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    FRAME_INTERVAL,
    DENSITY_WINDOW_SECONDS,
    TRAFFIC_LOW_THRESHOLD,
    TRAFFIC_MEDIUM_THRESHOLD,
)
from ai.pothole.config import (
    DEFAULT_POTHOLE_MODEL,
    POTHOLE_IMGSZ,
    POTHOLE_CONFIDENCE_THRESHOLD,
    POTHOLE_IOU_THRESHOLD,
    POTHOLE_MIN_EVENT_FRAMES,
    POTHOLE_FRAME_GAP_TOLERANCE,
    POTHOLE_TRACKING_IOU_THRESHOLD,
)

from ai.common.device import get_device_info
from ai.common.schemas import ProcessingConfig, ProcessingStatus, VideoMetadata
from ai.common.timing import TimingStats
from ai.detection.classes import get_phase1_class_ids
from ai.tracking.tracker import ByteTracker
from ai.traffic.density import DensityCalculator
from ai.traffic.vehicle_counter import VehicleCounter
from ai.pothole.detector import PotholeDetector, PotholeDetectorConfig
from ai.unified.schemas import UnifiedVideoSummary, UnifiedFrameResult
from ai.unified.events import UnifiedEventEngine, WaterloggingEventEngine
from ai.waterlogging.detector import WaterloggingDetector, WaterloggingDetectorConfig, ModelNotFoundError
from ai.waterlogging.config import (
    DEFAULT_WATERLOGGING_MODEL,
    WATERLOGGING_IMGSZ,
    WATERLOGGING_CONFIDENCE_THRESHOLD,
    WATERLOGGING_IOU_THRESHOLD,
    WATERLOGGING_MIN_EVENT_FRAMES,
    WATERLOGGING_FRAME_GAP_TOLERANCE,
    WATERLOGGING_TRACKING_IOU_THRESHOLD,
    WATERLOGGING_ENABLED,
)

from video.reader import read_video_info, iter_frames, VideoReadError
from video.sampler import FrameSampler, SamplerConfig
import ultralytics

import ultralytics

logger = logging.getLogger(__name__)

class UnifiedModelCache:
    """Singleton cache for ML models to avoid reloading them per-video."""
    _instance = None
    
    def __init__(self):
        self.device = get_device_info().device_str
        logger.info(f"Initializing Global Model Cache on {self.device}...")
        
        # Vehicle
        self.vehicle_model = YOLO(PRODUCTION_MODEL)
        self.vehicle_model.to(self.device)
        self.class_filter = get_phase1_class_ids(self.vehicle_model.names)
        
        # Pothole
        self.pothole_detector = PotholeDetector(
            config=PotholeDetectorConfig(
                model_path=DEFAULT_POTHOLE_MODEL,
                imgsz=POTHOLE_IMGSZ,
                confidence_threshold=POTHOLE_CONFIDENCE_THRESHOLD,
                iou_threshold=POTHOLE_IOU_THRESHOLD,
            )
        )
        self.pothole_detector.load()
        
        # Waterlogging
        if WATERLOGGING_ENABLED:
            self.waterlogging_detector = WaterloggingDetector(
                config=WaterloggingDetectorConfig(
                    model_path=DEFAULT_WATERLOGGING_MODEL,
                    imgsz=WATERLOGGING_IMGSZ,
                    confidence_threshold=WATERLOGGING_CONFIDENCE_THRESHOLD,
                    iou_threshold=WATERLOGGING_IOU_THRESHOLD,
                )
            )
            self.waterlogging_detector.load()
        else:
            self.waterlogging_detector = None
            
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

class UnifiedVideoProcessor:
    """
    Unified Phase 3 Video AI Processor.
    Processes both vehicle and pothole intelligence simultaneously.
    """

    def __init__(self) -> None:
        self.device_info = get_device_info()
        self.device = self.device_info.device_str

        # Timing stats
        self._timing_vehicle_inf = TimingStats("vehicle_inference")
        self._timing_pothole_inf = TimingStats("pothole_inference")
        self._timing_waterlogging_inf = TimingStats("waterlogging_inference")
        self._timing_tracking = TimingStats("tracking")
        self._timing_total = TimingStats("total_frame")

    def process(
        self,
        video_path: str,
        video_id: str,
        results_dir: str,
        progress_callback=None,
    ) -> UnifiedVideoSummary:
        
        logger.info("[VIDEO] job=%s upload_saved path=%s", video_id, video_path)

        # 1. Metadata
        try:
            video_info = read_video_info(video_path)
        except VideoReadError as exc:
            logger.error("[VIDEO] job=%s status=failed error=%s", video_id, exc)
            return self._error_result(video_id, video_path, str(exc))

        video_meta = VideoMetadata(
            video_id=video_id,
            filename=os.path.basename(video_path),
            width=video_info.width,
            height=video_info.height,
            fps=video_info.fps,
            frame_count=video_info.frame_count,
            duration_seconds=video_info.duration_seconds,
            codec=video_info.codec,
            file_size_bytes=video_info.file_size_bytes,
        )

        proc_config = ProcessingConfig(
            device=self.device,
            model_name=f"{PRODUCTION_MODEL} + {DEFAULT_POTHOLE_MODEL} + {DEFAULT_WATERLOGGING_MODEL}",
            imgsz=max(INFERENCE_IMGSZ, POTHOLE_IMGSZ, WATERLOGGING_IMGSZ),
            confidence_threshold=CONFIDENCE_THRESHOLD,
            iou_threshold=IOU_THRESHOLD,
            frame_interval=FRAME_INTERVAL,
            batch_size=1,
            ultralytics_version=ultralytics.__version__,
            torch_version=str(torch.__version__),
        )

        # 2. Load Models (Singleton)
        try:
            cache = UnifiedModelCache.get_instance()
            vehicle_model = cache.vehicle_model
            class_filter = cache.class_filter
            pothole_detector = cache.pothole_detector
            waterlogging_detector = cache.waterlogging_detector
        except ModelNotFoundError as exc:
            logger.error("Unified model missing: %s", exc)
            error_payload = json.dumps({
                "success": False,
                "error": "MODEL_NOT_FOUND",
                "resolved_path": exc.resolved_path,
                "exists": False
            })
            return self._error_result(video_id, video_path, error_payload)

        except Exception as exc:
            logger.error("Unified model load failed: %s", exc)
            return self._error_result(video_id, video_path, f"Model load failed: {exc}")

        # 3. Analytics Engines
        tracker = ByteTracker(model=vehicle_model, device=self.device)
        vehicle_counter = VehicleCounter()
        density_calc = DensityCalculator(
            window_seconds=DENSITY_WINDOW_SECONDS,
            low_threshold=TRAFFIC_LOW_THRESHOLD,
            medium_threshold=TRAFFIC_MEDIUM_THRESHOLD,
            video_duration=video_info.duration_seconds,
        )
        
        event_engine = UnifiedEventEngine(
            frame_width=video_info.width,
            frame_height=video_info.height,
            tracker_kwargs={
                "min_event_frames": POTHOLE_MIN_EVENT_FRAMES,
                "frame_gap_tolerance": POTHOLE_FRAME_GAP_TOLERANCE,
                "iou_threshold": POTHOLE_TRACKING_IOU_THRESHOLD
            }
        )
        
        waterlogging_event_engine = WaterloggingEventEngine(
            frame_width=video_info.width,
            frame_height=video_info.height,
            tracker_kwargs={
                "min_event_frames": WATERLOGGING_MIN_EVENT_FRAMES,
                "frame_gap_tolerance": WATERLOGGING_FRAME_GAP_TOLERANCE,
                "iou_threshold": WATERLOGGING_TRACKING_IOU_THRESHOLD
            }
        )

        # 4. Process Frames
        frame_results: list[UnifiedFrameResult] = []
        sampler_config = SamplerConfig(interval=FRAME_INTERVAL)
        # Stream frames lazily — do NOT load all into memory first.
        frame_iterator = list(FrameSampler(sampler_config).iter(video_path))
        total_frames = len(frame_iterator)

        logger.info(
            "[VIDEO] job=%s video_opened frames=%d fps=%.1f duration=%.1fs device=%s",
            video_id, total_frames, video_info.fps, video_info.duration_seconds, self.device
        )
        logger.info("[VIDEO] job=%s processor_started", video_id)

        for i, (frame_index, timestamp, frame) in enumerate(frame_iterator):
            t0 = time.perf_counter()

            # A. Vehicle Pipeline
            try:
                tracks, frame_timer = tracker.update(
                    frame=frame,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    confidence_threshold=CONFIDENCE_THRESHOLD,
                    iou_threshold=IOU_THRESHOLD,
                    imgsz=INFERENCE_IMGSZ,
                    class_filter=class_filter,
                )
            except Exception as exc:
                logger.warning("Tracking failed on frame %d: %s", frame_index, exc)
                tracks = []
                frame_timer = None
                
            vehicle_counter.update(tracks)
            density_calc.add_frame(timestamp, tracks)
            active_vehicle_ids = vehicle_counter.get_active_vehicle_ids_in_frame(tracks)

            # B. Pothole Pipeline
            pothole_dets, pt_prof = pothole_detector.detect(frame, frame_index, timestamp)
            
            # C. Fused Intelligence (Interaction, ROI, Tracking)
            active_pothole_ids = event_engine.update(
                frame_index=frame_index, 
                timestamp=timestamp, 
                raw_detections=pothole_dets,
                vehicle_tracks=tracks
            )
            
            # D. Waterlogging Pipeline (disabled if WATERLOGGING_ENABLED=False)
            if WATERLOGGING_ENABLED and waterlogging_detector is not None:
                waterlogging_dets, wl_prof = waterlogging_detector.detect(frame, frame_index, timestamp)
                active_waterlogging_ids = waterlogging_event_engine.update(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    raw_detections=waterlogging_dets,
                    vehicle_tracks=tracks
                )
            else:
                waterlogging_dets = []
                active_waterlogging_ids = []
                wl_prof = None

            frame_result = UnifiedFrameResult(
                frame_index=frame_index,
                timestamp=timestamp,
                vehicle_tracks=tracks,
                unique_vehicle_count_in_frame=len(active_vehicle_ids),
                pothole_detections=pothole_dets,
                active_pothole_event_ids=active_pothole_ids,
                waterlogging_detections=waterlogging_dets,
                active_waterlogging_event_ids=active_waterlogging_ids
            )
            frame_results.append(frame_result)

            frame_total_ms = (time.perf_counter() - t0) * 1000.0
            self._timing_total.record(frame_total_ms)
            if frame_timer:
                self._timing_vehicle_inf.record(frame_timer.inference_ms)
                self._timing_tracking.record(frame_timer.tracking_ms)
            if pt_prof:
                self._timing_pothole_inf.record(pt_prof.inference_ms)
            if wl_prof:
                self._timing_waterlogging_inf.record(wl_prof.inference_ms)

            if progress_callback:
                progress_callback(
                    i + 1,
                    total_frames,
                    self._timing_total.fps,
                    len(vehicle_counter.get_active_vehicle_ids_in_frame(tracks)),
                    len(event_engine.active_events) if hasattr(event_engine, "active_events") else 0
                )

            if (i + 1) % 100 == 0 or (i + 1) == total_frames:
                logger.info(
                    "[VIDEO] job=%s processing frame=%d/%d (%.0f%%)",
                    video_id, i + 1, total_frames, (i + 1) / total_frames * 100
                )

            # Yield the GIL every 5 frames so uvicorn can serve HTTP status polls
            # without starving while MPS/CPU is saturated by inference.
            if (i + 1) % 5 == 0:
                time.sleep(0)

        # 5. Final Analytics
        vehicle_count_summary = vehicle_counter.get_summary()
        density_windows = density_calc.compute_windows()
        unified_events = event_engine.finalize()
        waterlogging_events = waterlogging_event_engine.finalize()

        timing = {
            "total_frame": self._timing_total.to_dict(),
            "vehicle_inference": self._timing_vehicle_inf.to_dict(),
            "pothole_inference": self._timing_pothole_inf.to_dict(),
            "waterlogging_inference": self._timing_waterlogging_inf.to_dict(),
            "tracking": self._timing_tracking.to_dict(),
        }

        result = UnifiedVideoSummary(
            video=video_meta,
            processing=proc_config,
            status=ProcessingStatus.COMPLETED,
            frames=frame_results,
            vehicle_counts=vehicle_count_summary,
            density_windows=density_windows,
            pothole_events=unified_events,
            waterlogging_events=waterlogging_events,
            timing=timing,
        )

        # 6. Save
        # Phase 3 unified output
        os.makedirs(results_dir, exist_ok=True)
        result_path = os.path.join(results_dir, f"{video_id}_unified.json")
        with open(result_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)
            
        # Phase 5 forensic output
        phase5_dir = os.path.join(results_dir, "phase5")
        os.makedirs(phase5_dir, exist_ok=True)
        
        rejection_stats_path = os.path.join(phase5_dir, f"{video_id}_rejection_statistics.json")
        with open(rejection_stats_path, "w") as f:
            json.dump(event_engine.rejection_stats.model_dump(), f, indent=2)

        pothole_events_path = os.path.join(phase5_dir, f"{video_id}_pothole_events.json")
        with open(pothole_events_path, "w") as f:
            # Dump list of events
            events_dump = [e.model_dump() for e in unified_events]
            json.dump(events_dump, f, indent=2)

        logger.info("[VIDEO] job=%s processor_finished", video_id)
        logger.info(
            "[VIDEO] job=%s status=completed frames=%d fps=%.1f pothole_events=%d waterlogging_events=%d",
            video_id, total_frames, self._timing_total.fps, len(unified_events), len(waterlogging_events)
        )
        logger.info("Phase 5 Rejection Stats: %s", event_engine.rejection_stats.model_dump())

        return result

    def _error_result(self, video_id: str, video_path: str, error: str) -> UnifiedVideoSummary:
        return UnifiedVideoSummary(
            video=VideoMetadata(
                video_id=video_id,
                filename=os.path.basename(video_path),
                width=0, height=0, fps=0.0, frame_count=0, duration_seconds=0.0
            ),
            processing=ProcessingConfig(
                device=self.device,
                model_name=f"{PRODUCTION_MODEL} + {DEFAULT_POTHOLE_MODEL}",
                imgsz=640,
                confidence_threshold=0.25,
                iou_threshold=0.45,
                frame_interval=1,
                batch_size=1,
                torch_version=str(torch.__version__)
            ),
            status=ProcessingStatus.FAILED,
            error=error
        )
