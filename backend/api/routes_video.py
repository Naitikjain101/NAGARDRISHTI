"""
Urban Watch — Video API Routes

POST   /api/video/upload
GET    /api/video/{video_id}/metadata
GET    /api/video/{video_id}/stream
DELETE /api/video/{video_id}

Design decision:
  Upload saves the file LOCALLY only and returns immediately.
  Supabase Storage upload happens in the background AFTER AI processing completes.
  This prevents the HTTP upload from hanging on a slow/unavailable Storage service.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ai.common.schemas import VideoMetadata, VideoUploadResponse
from video.reader import read_video_info, VideoReadError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])

# Populated by main.py
UPLOAD_DIR: Path = Path("uploads")
RESULTS_DIR: Path = Path("results")


def set_directories(upload_dir: Path, results_dir: Path) -> None:
    global UPLOAD_DIR, RESULTS_DIR
    UPLOAD_DIR = upload_dir
    RESULTS_DIR = results_dir


ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "application/octet-stream",  # some browsers use this for .mp4
}

MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024   # 500 MB — matches UI and config.py


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file.

    Saves file locally, validates with OpenCV, returns immediately.
    Supabase Storage upload happens later (post-AI, in the background).
    Never blocks on remote Storage calls.
    """
    # Content-type check (best-effort; browsers vary)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning("Rejected upload: content_type=%s filename=%s", file.content_type, file.filename)
        raise HTTPException(status_code=415, detail="Unsupported media type. Use MP4, AVI, MOV, MKV, or WebM.")

    # Size check before reading into memory
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty (0 bytes).")

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."
        )

    # Generate stable video_id and sanitize filename
    video_id = str(uuid.uuid4())
    safe_original_name = "".join(
        c for c in (file.filename or "video.mp4") if c.isalnum() or c in ".-_"
    ).strip()
    suffix = Path(safe_original_name).suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        suffix = ".mp4"

    dest_path = UPLOAD_DIR / f"{video_id}{suffix}"

    # Write to disk
    try:
        import shutil
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        logger.error("Failed to write upload to disk: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    # Validate with OpenCV — reject corrupt/unreadable videos immediately
    try:
        info = read_video_info(str(dest_path))
    except VideoReadError as exc:
        dest_path.unlink(missing_ok=True)
        logger.warning("Rejected corrupt video upload video_id=%s: %s", video_id, exc)
        raise HTTPException(status_code=422, detail=f"Invalid or corrupt video file: {exc}")

    logger.info(
        "[VIDEO] upload_saved video_id=%s filename=%s %dx%d %.1ffps %d frames %.1fMB",
        video_id, safe_original_name,
        info.width, info.height, info.fps, info.frame_count,
        info.file_size_bytes / (1024 * 1024),
    )

    return VideoUploadResponse(
        video_id=video_id,
        filename=safe_original_name,
        metadata=VideoMetadata(
            video_id=video_id,
            filename=safe_original_name,
            width=info.width,
            height=info.height,
            fps=info.fps,
            frame_count=info.frame_count,
            duration_seconds=info.duration_seconds,
            codec=info.codec,
            file_size_bytes=info.file_size_bytes,
        ),
    )


@router.get("/{video_id}/metadata", response_model=VideoMetadata)
async def get_video_metadata(video_id: str):
    """Return video metadata for a previously uploaded video."""
    video_path = _find_video(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        info = read_video_info(str(video_path))
    except VideoReadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return VideoMetadata(
        video_id=video_id,
        filename=video_path.name,
        width=info.width,
        height=info.height,
        fps=info.fps,
        frame_count=info.frame_count,
        duration_seconds=info.duration_seconds,
        codec=info.codec,
        file_size_bytes=info.file_size_bytes,
    )


@router.get("/{video_id}/frame")
async def get_video_frame(video_id: str, time: float = 0.0, bbox: str = None, label: str = None):
    """
    Extract a single frame from the video at the given timestamp.
    Optionally draw a bounding box if bbox (x1,y1,x2,y2) is provided.
    """
    video_path = _find_video(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not found")

    import cv2
    from fastapi.responses import Response
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Cannot open video file")

    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    # Some OpenCV backends (like FFmpeg) seek to keyframes with POS_MSEC. 
    # For precise seeking, POS_FRAMES is often more accurate.
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps > 0:
        target_frame = int(time * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise HTTPException(status_code=404, detail="Could not read frame at the specified time")

    if bbox:
        try:
            x1, y1, x2, y2 = map(float, bbox.split(","))
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Draw bounding box
            color = (0, 165, 255) # Orange in BGR
            if label and "water" in label.lower():
                color = (255, 130, 59) # Blue in BGR
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            
            if label:
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frame, label.upper(), (x1, max(y1 - 10, 10)), font, 0.9, color, 2, cv2.LINE_AA)
        except Exception as e:
            logger.warning(f"Failed to draw bbox on frame: {e}")

    success, buffer = cv2.imencode('.jpg', frame)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode frame")

    return Response(content=buffer.tobytes(), media_type="image/jpeg")


@router.get("/{video_id}/stream")
async def stream_video(video_id: str):
    """
    Stream / serve the video to the browser.

    Priority:
      1. Serve from local disk (fast, always available during processing)
      2. Redirect to Supabase signed URL (fallback if file was cleaned up)
    """
    # Primary: serve locally
    video_path = _find_video(video_id)
    if video_path and video_path.exists():
        media_type = _suffix_to_mime(video_path.suffix)
        logger.debug("[VIDEO] stream_local video_id=%s path=%s", video_id, video_path)
        return FileResponse(str(video_path), media_type=media_type)

    # Fallback: try Supabase signed URL
    try:
        from db.supabase_client import get_supabase
        from fastapi.responses import RedirectResponse
        client = get_supabase()
        bucket = "urban_watch_evidence"

        # Since supabase-py removed 'search' kwarg, we'll just check common extensions.
        # Alternatively, we could do `list(path="uploads")` and filter in Python.
        # To avoid listing 10,000 files, we just assume it's .mp4 (standard for urban watch).
        # We generate a signed URL directly. If it doesn't exist, Supabase returns 404 to the browser.
        filename = f"{video_id}.mp4"
        storage_path = f"uploads/{filename}"
        signed = client.storage.from_(bucket).create_signed_url(storage_path, 3600)
        if "signedURL" in signed:
            return RedirectResponse(url=signed["signedURL"])
    except Exception as storage_exc:
        logger.warning("[VIDEO] stream_storage_fallback_failed video_id=%s: %s", video_id, storage_exc)

    raise HTTPException(status_code=404, detail="Video not found locally or in storage")


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and its AI results from local disk and Storage (best-effort)."""
    deleted: list[str] = []

    video_path = _find_video(video_id)
    if video_path and video_path.exists():
        video_path.unlink()
        deleted.append("local_video")

    for stem in (f"{video_id}.json", f"{video_id}_unified.json"):
        p = RESULTS_DIR / stem
        if p.exists():
            p.unlink()
            deleted.append(f"local_{stem}")

    # Best-effort Storage cleanup
    try:
        from db.supabase_client import get_supabase
        client = get_supabase()
        bucket = "urban_watch_evidence"
        filename = f"{video_id}.mp4"
        client.storage.from_(bucket).remove([f"uploads/{filename}"])
        deleted.append("storage_video")
    except Exception as exc:
        logger.warning("[VIDEO] storage delete failed video_id=%s: %s", video_id, exc)

    return {"deleted": deleted, "video_id": video_id}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_video(video_id: str) -> Path | None:
    # Strip suffix from video_id if it's already there to prevent double extension
    clean_id = video_id
    for s in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        if video_id.endswith(s):
            clean_id = video_id[:-len(s)]
            break

    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        path = UPLOAD_DIR / f"{clean_id}{suffix}"
        if path.exists():
            return path
            
    # Also check demo_videos using exact name or suffix
    demo_path1 = Path("demo_videos") / video_id
    if demo_path1.exists():
        return demo_path1
    
    demo_path2 = Path("demo_videos") / f"{clean_id}.mp4"
    if demo_path2.exists():
        return demo_path2

    # Finally check if there's any file in demo_videos whose name is contained in the clean_id
    if Path("demo_videos").exists():
        for f in Path("demo_videos").iterdir():
            if f.is_file() and not f.name.startswith('.'):
                if f.stem in clean_id:
                    return f

    return None


def _suffix_to_mime(suffix: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(suffix.lower(), "video/mp4")
