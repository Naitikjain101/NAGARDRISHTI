"""
Urban Watch — Video Processor (End-to-End Pipeline)

Orchestrates:
  VideoReader → FrameSampler → Tracker → VehicleCounter → DensityCalculator

Produces timestamped JSON results.

Rules:
- Runs in a background thread (does NOT block video playback)
- Never stores images inside JSON
- Never fabricates detections or counts
- Records actual device, model, config used
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

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
from ai.common.device import get_device_info
from ai.common.schemas import (
    FrameResult,
    ProcessingConfig,
    ProcessingResult,
    ProcessingStatus,
    VideoMetadata,
)
from ai.common.timing import TimingStats
from ai.detection.classes import get_phase1_class_ids
from ai.tracking.tracker import ByteTracker
from ai.traffic.density import DensityCalculator
from ai.traffic.vehicle_counter import VehicleCounter
from video.reader import read_video_info, iter_frames, VideoReadError
from video.sampler import FrameSampler, SamplerConfig

import ultralytics

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    End-to-end video AI processing pipeline.

    Usage:
        processor = VideoProcessor()
        result = processor.process(video_path, video_id)
    """

    def __init__(
        self,
        model_name: str | None = None,
        imgsz: int | None = None,
        confidence_threshold: float | None = None,
        iou_threshold: float | None = None,
        frame_interval: int | None = None,
    ) -> None:
        import torch

        self.model_name = model_name or PRODUCTION_MODEL
        self.imgsz = imgsz or INFERENCE_IMGSZ
        self.confidence_threshold = confidence_threshold or CONFIDENCE_THRESHOLD
        self.iou_threshold = iou_threshold or IOU_THRESHOLD
        self.frame_interval = frame_interval or FRAME_INTERVAL

        # Detect device
        self.device_info = get_device_info()
        self.device = self.device_info.device_str

        # Timing stats
        self._timing_inference = TimingStats("inference")
        self._timing_tracking = TimingStats("tracking")
        self._timing_total = TimingStats("total_frame")

        logger.info(
            "VideoProcessor init: model=%s, device=%s, imgsz=%d, conf=%.2f",
            self.model_name, self.device, self.imgsz, self.confidence_threshold,
        )

    def process(
        self,
        video_path: str,
        video_id: str,
        results_dir: str,
        progress_callback=None,
    ) -> ProcessingResult:
        """
        Process a video file end-to-end.

        Parameters
        ----------
        video_path : str
            Path to the source video file.
        video_id : str
            Unique identifier for this video.
        results_dir : str
            Directory where the result JSON will be saved.
        progress_callback : callable or None
            Called with (processed_frames, total_frames) for progress reporting.

        Returns
        -------
        ProcessingResult
            Complete AI results including all frames, counts, density.
        """
        import torch
        from ultralytics import YOLO

        # -------------------------------------------------------------------------
        # Step 1: Read video metadata
        # -------------------------------------------------------------------------
        try:
            video_info = read_video_info(video_path)
        except VideoReadError as exc:
            logger.error("Cannot process video %s: %s", video_id, exc)
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
            model_name=self.model_name,
            imgsz=self.imgsz,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            frame_interval=self.frame_interval,
            batch_size=1,
            ultralytics_version=ultralytics.__version__,
            torch_version=str(torch.__version__),
        )

        # -------------------------------------------------------------------------
        # Step 2: Load model
        # -------------------------------------------------------------------------
        try:
            model = YOLO(self.model_name)
            model.to(self.device)
            class_filter = get_phase1_class_ids(model.names)
            logger.info("Model loaded: %s, class_filter=%s", self.model_name, class_filter)
        except Exception as exc:
            logger.error("Model load failed: %s", exc)
            return self._error_result(video_id, video_path, f"Model load failed: {exc}")

        # -------------------------------------------------------------------------
        # Step 3: Initialize tracker and analytics
        # -------------------------------------------------------------------------
        tracker = ByteTracker(
            model=model,
            device=self.device,
        )
        vehicle_counter = VehicleCounter()
        density_calc = DensityCalculator(
            window_seconds=DENSITY_WINDOW_SECONDS,
            low_threshold=TRAFFIC_LOW_THRESHOLD,
            medium_threshold=TRAFFIC_MEDIUM_THRESHOLD,
            video_duration=video_info.duration_seconds,
        )

        # -------------------------------------------------------------------------
        # Step 4: Process frames
        # -------------------------------------------------------------------------
        frame_results: list[FrameResult] = []
        sampler_config = SamplerConfig(interval=self.frame_interval)
        sampled_frames = list(
            FrameSampler(sampler_config).iter(video_path)
        )
        total_frames = len(sampled_frames)

        logger.info(
            "Processing %d frames (interval=%d) from %s",
            total_frames, self.frame_interval, os.path.basename(video_path),
        )

        for i, (frame_index, timestamp, frame) in enumerate(sampled_frames):
            t0 = time.perf_counter()

            try:
                tracks, frame_timer = tracker.update(
                    frame=frame,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    confidence_threshold=self.confidence_threshold,
                    iou_threshold=self.iou_threshold,
                    imgsz=self.imgsz,
                    class_filter=class_filter,
                )
            except Exception as exc:
                logger.warning(
                    "Tracking failed on frame %d: %s", frame_index, exc
                )
                tracks = []
                frame_timer = None

            # Update analytics
            vehicle_counter.update(tracks)
            density_calc.add_frame(timestamp, tracks)

            # Active vehicle count in this frame
            active_vehicle_ids = vehicle_counter.get_active_vehicle_ids_in_frame(tracks)

            frame_result = FrameResult(
                frame_index=frame_index,
                timestamp=timestamp,
                detections=[],   # raw detections skipped when tracking is used
                tracks=tracks,
                unique_vehicle_count_in_frame=len(active_vehicle_ids),
            )
            frame_results.append(frame_result)

            frame_total_ms = (time.perf_counter() - t0) * 1000.0
            self._timing_total.record(frame_total_ms)
            if frame_timer:
                self._timing_tracking.record(frame_timer.tracking_ms)

            if progress_callback:
                progress_callback(i + 1, total_frames)

        # -------------------------------------------------------------------------
        # Step 5: Compute final analytics
        # -------------------------------------------------------------------------
        vehicle_count_summary = vehicle_counter.get_summary()
        density_windows = density_calc.compute_windows()
        tracking_quality = tracker.get_quality_metrics()

        # -------------------------------------------------------------------------
        # Step 6: Build result
        # -------------------------------------------------------------------------
        timing = {
            "total_frame": self._timing_total.to_dict(),
            "tracking": self._timing_tracking.to_dict(),
            "tracking_quality": tracking_quality,
        }

        result = ProcessingResult(
            video=video_meta,
            processing=proc_config,
            status=ProcessingStatus.COMPLETE,
            frames=frame_results,
            vehicle_counts=vehicle_count_summary,
            density_windows=density_windows,
            timing=timing,
        )

        # -------------------------------------------------------------------------
        # Step 7: Save to results directory
        # -------------------------------------------------------------------------
        os.makedirs(results_dir, exist_ok=True)
        result_path = os.path.join(results_dir, f"{video_id}.json")
        with open(result_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)

        logger.info(
            "Processing complete: %s — %d frames, %d unique vehicles, %.1f avg FPS",
            video_id,
            len(frame_results),
            vehicle_count_summary.total_unique_vehicles,
            self._timing_total.fps,
        )

        return result

    def _error_result(
        self,
        video_id: str,
        video_path: str,
        error: str,
    ) -> ProcessingResult:
        """Build a failed ProcessingResult."""
        import torch
        return ProcessingResult(
            video=VideoMetadata(
                video_id=video_id,
                filename=os.path.basename(video_path),
                width=0,
                height=0,
                fps=0.0,
                frame_count=0,
                duration_seconds=0.0,
            ),
            processing=ProcessingConfig(
                device=self.device,
                model_name=self.model_name,
                imgsz=self.imgsz,
                confidence_threshold=self.confidence_threshold,
                iou_threshold=self.iou_threshold,
                frame_interval=self.frame_interval,
                batch_size=1,
                torch_version=str(torch.__version__),
            ),
            status=ProcessingStatus.FAILED,
            error=error,
        )
