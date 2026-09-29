"""
Urban Watch — High-Precision Timing Utilities

Provides microsecond-resolution timing for benchmarking.
All timing values are in milliseconds unless noted.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class TimingStats:
    """Accumulated timing statistics over multiple measurements."""

    name: str
    values_ms: list[float] = field(default_factory=list)

    def record(self, ms: float) -> None:
        self.values_ms.append(ms)

    @property
    def count(self) -> int:
        return len(self.values_ms)

    @property
    def total_ms(self) -> float:
        return sum(self.values_ms)

    @property
    def mean_ms(self) -> float:
        if not self.values_ms:
            return 0.0
        return self.total_ms / len(self.values_ms)

    @property
    def min_ms(self) -> float:
        return min(self.values_ms) if self.values_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.values_ms) if self.values_ms else 0.0

    @property
    def fps(self) -> float:
        if self.mean_ms <= 0:
            return 0.0
        return 1000.0 / self.mean_ms

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "count": self.count,
            "mean_ms": round(self.mean_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "total_ms": round(self.total_ms, 3),
            "fps": round(self.fps, 2),
        }


@contextmanager
def timer(label: str = "") -> Generator[list[float], None, None]:
    """
    Context manager that records elapsed time in milliseconds.

    Usage:
        with timer("inference") as t:
            result = model(frame)
        elapsed_ms = t[0]
    """
    result: list[float] = [0.0]
    start = time.perf_counter()
    try:
        yield result
    finally:
        result[0] = (time.perf_counter() - start) * 1000.0


def now_ms() -> float:
    """Return current time in milliseconds (monotonic)."""
    return time.perf_counter() * 1000.0


class FrameTimer:
    """
    Per-frame timing breakdown for benchmarking.

    Records:
    - decode_ms
    - preprocess_ms
    - inference_ms
    - tracking_ms
    - serialization_ms
    - total_ms
    """

    def __init__(self) -> None:
        self.decode_ms: float = 0.0
        self.preprocess_ms: float = 0.0
        self.inference_ms: float = 0.0
        self.tracking_ms: float = 0.0
        self.serialization_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return (
            self.decode_ms
            + self.preprocess_ms
            + self.inference_ms
            + self.tracking_ms
            + self.serialization_ms
        )

    @property
    def fps(self) -> float:
        if self.total_ms <= 0:
            return 0.0
        return 1000.0 / self.total_ms

    def to_dict(self) -> dict:
        return {
            "decode_ms": round(self.decode_ms, 3),
            "preprocess_ms": round(self.preprocess_ms, 3),
            "inference_ms": round(self.inference_ms, 3),
            "tracking_ms": round(self.tracking_ms, 3),
            "serialization_ms": round(self.serialization_ms, 3),
            "total_ms": round(self.total_ms, 3),
            "fps": round(self.fps, 2),
        }
