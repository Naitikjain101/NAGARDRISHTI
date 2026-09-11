"""
Phase 10 — Step 21: AI Validation/Forensic Mode
Development-only endpoint that processes a video through the full waterlogging
pipeline and outputs RAW/VALIDATED/REJECTED/FINAL counts + rejection reasons
WITHOUT creating any production incidents in Supabase.

POST /api/ai/waterlogging/forensic
  Body: { "video_id": "...", "use_validator": true, "dump_rejected": true }

GET /api/ai/waterlogging/forensic/{job_id}
  Returns forensic report
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

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
from ai.waterlogging.validator import WaterloggingValidator, ValidationConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/waterlogging", tags=["waterlogging_forensic"])

# In-memory forensic report store (development only — not persisted to Supabase)
_forensic_reports: dict = {}
_forensic_lock = threading.Lock()


class ForensicRequest(BaseModel):
    video_id: str
    use_validator: bool = True
    dump_rejected: bool = True
    # Override validation thresholds for threshold sweep (Step 19)
    min_confidence: Optional[float] = None
    max_area_ratio_to_frame: Optional[float] = None


@router.post("/forensic")
async def start_forensic_analysis(req: ForensicRequest, background_tasks: BackgroundTasks):
    """
    Step 21: Development forensic mode.
    Runs the complete waterlogging pipeline on an uploaded video and returns
    RAW / VALIDATED / REJECTED / FINAL EVENT counts with rejection reasons.
    Does NOT create any Supabase incidents.
    """
    UPLOAD_DIR = Path("uploads")
    video_path = None
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        p = UPLOAD_DIR / f"{req.video_id}{suffix}"
        if p.exists():
            video_path = p
            break

    if video_path is None:
        raise HTTPException(status_code=404, detail=f"Video {req.video_id} not found in uploads/")

    with _forensic_lock:
        _forensic_reports[req.video_id] = {
            "status": "running",
            "video_id": req.video_id,
            "waterlogging_enabled_flag": WATERLOGGING_ENABLED,
        }

    background_tasks.add_task(
        _run_forensic_pipeline,
        video_id=req.video_id,
        video_path=str(video_path),
        use_validator=req.use_validator,
        dump_rejected=req.dump_rejected,
        min_confidence_override=req.min_confidence,
        max_area_ratio_override=req.max_area_ratio_to_frame,
    )

    return {
        "status": "started",
        "video_id": req.video_id,
        "note": (
            "FORENSIC MODE: No Supabase incidents will be created. "
            "Poll GET /api/ai/waterlogging/forensic/{video_id} for results."
        ),
    }


@router.get("/forensic/{video_id}")
async def get_forensic_report(video_id: str):
    """Retrieve the forensic analysis report for a video."""
    with _forensic_lock:
        report = _forensic_reports.get(video_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No forensic report found for this video_id")
    return report


@router.get("/status")
async def waterlogging_status():
    """Returns whether waterlogging is enabled and the current model version/checksum."""
    from ai.waterlogging.model_registry import load_and_verify_model, WATERLOGGING_MODELS_DIR
    import json

    status = {
        "waterlogging_enabled": WATERLOGGING_ENABLED,
        "model_path": DEFAULT_WATERLOGGING_MODEL,
        "phase10_safety_reason": (
            "Disabled per Phase 10 Step 0: V1 model has Precision=0.00 on unseen video. "
            "Re-enable only after Steps 1-21 pass."
            if not WATERLOGGING_ENABLED else "Enabled"
        ),
    }

    # Try to load metadata.json for active model version (v2)
    try:
        # Prefer v2 metadata; fall back to v1 if not yet present
        for version in ("v2", "v1"):
            meta_path = WATERLOGGING_MODELS_DIR / version / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                status["model_version"] = meta.get("version")
                status["model_sha256"] = meta.get("sha256", "")[:16] + "..."
                status["model_production_status"] = meta.get("production_status")
                # V2 doesn't have known_limitations — report val metrics instead
                if version == "v2":
                    fm = meta.get("final_metrics", {})
                    status["model_val_metrics"] = {
                        "mask_mAP50":    fm.get("metrics/mask_mAP50(M)") or fm.get("mask_mAP50"),
                        "mask_mAP50_95": fm.get("metrics/mask_mAP50-95(M)") or fm.get("mask_mAP50_95"),
                        "box_precision": fm.get("metrics/precision(B)"),
                        "box_recall":    fm.get("metrics/recall(B)"),
                    }
                else:
                    status["known_limitations"] = meta.get("known_limitations")
                break
    except Exception as e:
        status["metadata_error"] = str(e)

    return status


def _run_forensic_pipeline(
    video_id: str,
    video_path: str,
    use_validator: bool,
    dump_rejected: bool,
    min_confidence_override: Optional[float],
    max_area_ratio_override: Optional[float],
):
    """Background task: run waterlogging-only pipeline without creating Supabase incidents."""
    import cv2
    import time
    from ultralytics import YOLO
    from ai.waterlogging.detector import WaterloggingDetector, WaterloggingDetectorConfig
    from ai.waterlogging.model_registry import load_and_verify_model
    from ai.waterlogging.schemas import WaterloggingDetection
    from ai.unified.events import WaterloggingEventEngine

    t_start = time.time()
    try:
        model_path = load_and_verify_model("v1")
        logger.info("[FORENSIC] job=%s model_verified path=%s", video_id, model_path)

        # Build validation config (allow per-request overrides for Step 19 threshold sweep)
        val_config = ValidationConfig()
        if min_confidence_override is not None:
            val_config.min_confidence = min_confidence_override
        if max_area_ratio_override is not None:
            val_config.max_area_ratio_to_frame = max_area_ratio_override

        detector = WaterloggingDetector(
            config=WaterloggingDetectorConfig(
                model_path=str(model_path),
                imgsz=WATERLOGGING_IMGSZ,
                confidence_threshold=WATERLOGGING_CONFIDENCE_THRESHOLD,
                iou_threshold=WATERLOGGING_IOU_THRESHOLD,
            )
        )
        detector.load()

        cap = cv2.VideoCapture(video_path)
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        engine = WaterloggingEventEngine(
            frame_width=frame_w,
            frame_height=frame_h,
            tracker_kwargs={
                "min_event_frames": WATERLOGGING_MIN_EVENT_FRAMES,
                "frame_gap_tolerance": WATERLOGGING_FRAME_GAP_TOLERANCE,
                "iou_threshold": WATERLOGGING_TRACKING_IOU_THRESHOLD,
            },
            validation_config=val_config if use_validator else None,
        )

        FRAME_INTERVAL = 29
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % FRAME_INTERVAL == 0:
                dets, _ = detector.detect(frame, frame_idx, frame_idx / max(1, cap.get(cv2.CAP_PROP_FPS)))
                engine.update(frame_idx, frame_idx / max(1, cap.get(cv2.CAP_PROP_FPS)), dets, [])
            frame_idx += 1
        cap.release()

        events = engine.finalize()
        forensic_report = engine.get_forensic_report()

        result = {
            "status": "completed",
            "video_id": video_id,
            "video_dims": [frame_w, frame_h],
            "total_frames": total_frames,
            "validation_config": {
                "use_validator": use_validator,
                "min_confidence": val_config.min_confidence,
                "max_area_ratio_to_frame": val_config.max_area_ratio_to_frame,
                "road_top_boundary": val_config.road_top_boundary,
            },
            "pipeline_counts": forensic_report,
            "final_events": len(events),
            "processing_seconds": round(time.time() - t_start, 1),
            "note": "FORENSIC MODE — no Supabase incidents created",
        }

        if dump_rejected and forensic_report.get("rejected_sample"):
            result["rejected_sample"] = forensic_report["rejected_sample"]

        with _forensic_lock:
            _forensic_reports[video_id] = result

        logger.info(
            "[FORENSIC] job=%s completed raw=%d validated=%d rejected=%d events=%d",
            video_id,
            forensic_report["raw_detections"],
            forensic_report["validated_detections"],
            forensic_report["rejected_detections"],
            len(events),
        )

    except Exception as exc:
        logger.error("[FORENSIC] job=%s failed: %s", video_id, exc, exc_info=True)
        with _forensic_lock:
            _forensic_reports[video_id] = {
                "status": "failed",
                "video_id": video_id,
                "error": str(exc),
                "processing_seconds": round(time.time() - t_start, 1),
            }
