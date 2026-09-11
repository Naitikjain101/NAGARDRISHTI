"""
Urban Watch — Video Reader

Extracts metadata and frames from video files.

Handles:
- Corrupted videos
- Zero-frame videos
- Unsupported codecs
- Missing files

Never modifies source video files.
Never re-encodes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VideoReadError(Exception):
    """Raised when a video cannot be opened or read."""
    pass


@dataclass(frozen=True)
class VideoInfo:
    """Metadata extracted from a video file."""

    path: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float
    codec: str | None
    file_size_bytes: int


def read_video_info(path: str | Path) -> VideoInfo:
    """
    Extract metadata from a video file.

    Parameters
    ----------
    path : str or Path
        Path to the video file.

    Returns
    -------
    VideoInfo
        Metadata about the video.

    Raises
    ------
    VideoReadError
        If the file is missing, corrupted, or unreadable.
    """
    path = str(path)

    # Check existence
    if not os.path.exists(path):
        raise VideoReadError(f"Video file not found: {path}")

    file_size = os.path.getsize(path)
    if file_size == 0:
        raise VideoReadError(f"Video file is empty (0 bytes): {path}")

    # Open with OpenCV
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoReadError(
            f"Cannot open video file: {path}. "
            "File may be corrupted or codec unsupported."
        )

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Codec (4-char code)
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = _decode_fourcc(fourcc_int)

    finally:
        cap.release()

    # Validate
    if width <= 0 or height <= 0:
        raise VideoReadError(
            f"Invalid video dimensions: {width}x{height} in {path}"
        )

    if fps <= 0:
        logger.warning(
            "Video %s has invalid FPS (%s). Defaulting to 25.0.", path, fps
        )
        fps = 25.0

    if frame_count <= 0:
        raise VideoReadError(
            f"Video has no frames (frame_count={frame_count}): {path}"
        )

    duration = frame_count / fps

    info = VideoInfo(
        path=path,
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_seconds=round(duration, 4),
        codec=codec,
        file_size_bytes=file_size,
    )

    logger.info(
        "Video info: %s — %dx%d @ %.2f fps, %d frames, %.2fs, codec=%s, size=%.1f MB",
        os.path.basename(path),
        width, height, fps, frame_count, duration, codec,
        file_size / (1024 * 1024),
    )

    return info


def iter_frames(
    path: str | Path,
    interval: int = 1,
    max_frames: int | None = None,
) -> Generator[tuple[int, float, np.ndarray], None, None]:
    """
    Yield (frame_index, timestamp, frame) tuples from a video.

    Parameters
    ----------
    path : str or Path
        Path to the video file.
    interval : int
        Frame sampling interval. 1 = every frame, 2 = every other frame.
    max_frames : int or None
        Maximum number of frames to yield. None = all frames.

    Yields
    ------
    (frame_index, timestamp_seconds, bgr_frame)

    Raises
    ------
    VideoReadError
        If the video cannot be opened.
    """
    path = str(path)

    if interval < 1:
        raise ValueError(f"interval must be >= 1, got {interval}")

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoReadError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    yielded = 0
    frame_index = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % interval == 0:
                timestamp = frame_index / fps
                yield frame_index, round(timestamp, 6), frame
                yielded += 1

                if max_frames is not None and yielded >= max_frames:
                    break

            frame_index += 1
    finally:
        cap.release()

    logger.debug(
        "iter_frames: yielded %d frames from %s (interval=%d)",
        yielded, os.path.basename(path), interval,
    )


def _decode_fourcc(fourcc_int: int) -> str | None:
    """Decode OpenCV FOURCC integer to a 4-character string."""
    try:
        chars = [
            chr((fourcc_int >> (8 * i)) & 0xFF)
            for i in range(4)
        ]
        codec = "".join(chars).strip()
        return codec if codec and codec.isprintable() else None
    except Exception:
        return None
