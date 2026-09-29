"""Tests for video reader."""

from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np
import pytest

from video.reader import read_video_info, iter_frames, VideoReadError


def _create_test_video(
    path: str,
    width: int = 640,
    height: int = 480,
    fps: float = 30.0,
    num_frames: int = 30,
) -> None:
    """Create a synthetic test video using OpenCV."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for i in range(num_frames):
        # Create a frame with a moving rectangle
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        x = (i * 10) % width
        cv2.rectangle(frame, (x, 100), (x + 50, 200), (0, 255, 0), -1)
        writer.write(frame)
    writer.release()


@pytest.fixture
def test_video(tmp_path):
    """Create a temporary test video."""
    path = str(tmp_path / "test.mp4")
    _create_test_video(path, width=640, height=480, fps=25.0, num_frames=50)
    return path


def test_read_video_info_basic(test_video):
    """read_video_info returns correct metadata."""
    info = read_video_info(test_video)
    assert info.width == 640
    assert info.height == 480
    assert info.fps > 0
    assert info.frame_count == 50
    assert info.duration_seconds > 0
    assert info.file_size_bytes > 0


def test_read_video_info_has_codec(test_video):
    """Codec must be extracted (may be None but not crash)."""
    info = read_video_info(test_video)
    # codec can be None or a 4-char string — both are valid
    if info.codec is not None:
        assert isinstance(info.codec, str)


def test_read_missing_file():
    """Missing file raises VideoReadError."""
    with pytest.raises(VideoReadError, match="not found"):
        read_video_info("/nonexistent/path/video.mp4")


def test_read_empty_file(tmp_path):
    """Empty file raises VideoReadError."""
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(VideoReadError, match="empty"):
        read_video_info(str(empty))


def test_read_corrupt_file(tmp_path):
    """Corrupt file raises VideoReadError."""
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"this is not a video file at all")
    with pytest.raises(VideoReadError):
        read_video_info(str(corrupt))


def test_iter_frames_yields_correct_count(test_video):
    """iter_frames at interval=1 yields all frames."""
    frames = list(iter_frames(test_video, interval=1))
    assert len(frames) == 50


def test_iter_frames_interval_2(test_video):
    """iter_frames at interval=2 yields roughly half the frames."""
    frames = list(iter_frames(test_video, interval=2))
    assert len(frames) == 25  # 50 frames / 2


def test_iter_frames_interval_3(test_video):
    """iter_frames at interval=3 yields roughly one-third of frames."""
    frames = list(iter_frames(test_video, interval=3))
    # 50 frames at interval=3: indices 0,3,6,...,48 → ceil(50/3) = 17
    assert len(frames) == 17


def test_iter_frames_yields_tuples(test_video):
    """Each yielded item is (int, float, ndarray)."""
    for frame_index, timestamp, frame in iter_frames(test_video, interval=10):
        assert isinstance(frame_index, int)
        assert isinstance(timestamp, float)
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3
        assert frame.shape[2] == 3  # BGR


def test_iter_frames_timestamps_monotonic(test_video):
    """Timestamps must be monotonically increasing."""
    timestamps = [ts for _, ts, _ in iter_frames(test_video, interval=1)]
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1]


def test_iter_frames_max_frames(test_video):
    """max_frames parameter limits the number of yielded frames."""
    frames = list(iter_frames(test_video, interval=1, max_frames=10))
    assert len(frames) == 10


def test_iter_frames_invalid_interval(test_video):
    """interval < 1 raises ValueError."""
    with pytest.raises(ValueError):
        list(iter_frames(test_video, interval=0))
