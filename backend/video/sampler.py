"""
Urban Watch — Frame Sampler

Controls which frames from a video are submitted to inference.

Phase 1 baseline: interval=1 (every frame).
Do NOT increase interval until an accuracy baseline is established.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from video.reader import iter_frames, VideoReadError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SamplerConfig:
    """Configuration for frame sampling."""

    interval: int = 1
    """1 = every frame, 2 = every other, 3 = every third."""

    max_frames: int | None = None
    """Maximum frames to yield. None = no limit."""

    def validate(self) -> None:
        if self.interval < 1:
            raise ValueError(f"interval must be >= 1, got {self.interval}")


class FrameSampler:
    """
    Iterates a video file and yields frames at the configured interval.

    Usage:
        sampler = FrameSampler(SamplerConfig(interval=1))
        for frame_index, timestamp, frame in sampler.iter(video_path):
            ...
    """

    def __init__(self, config: SamplerConfig | None = None) -> None:
        self.config = config or SamplerConfig()
        self.config.validate()

    def iter(self, video_path: str):
        """
        Yield (frame_index, timestamp, bgr_frame) tuples.

        Parameters
        ----------
        video_path : str
            Path to the video file.

        Yields
        ------
        (frame_index: int, timestamp: float, frame: np.ndarray)
        """
        logger.info(
            "Sampling %s at interval=%d",
            video_path,
            self.config.interval,
        )

        yield from iter_frames(
            video_path,
            interval=self.config.interval,
            max_frames=self.config.max_frames,
        )
