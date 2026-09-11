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
        content = await file.read()
        dest_path.write_bytes(content)
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

        res = client.storage.from_(bucket).list("uploads", search=video_id)
        if res and isinstance(res, list) and len(res) > 0:
            filename = res[0]["name"]
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
        res = client.storage.from_(bucket).list("uploads", search=video_id)
        if res and isinstance(res, list) and len(res) > 0:
            filename = res[0]["name"]
            client.storage.from_(bucket).remove([f"uploads/{filename}"])
            deleted.append("storage_video")
    except Exception as exc:
        logger.warning("[VIDEO] storage delete failed video_id=%s: %s", video_id, exc)

    return {"deleted": deleted, "video_id": video_id}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_video(video_id: str) -> Path | None:
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        path = UPLOAD_DIR / f"{video_id}{suffix}"
        if path.exists():
            return path
    return None


def _suffix_to_mime(suffix: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(suffix.lower(), "video/mp4")
