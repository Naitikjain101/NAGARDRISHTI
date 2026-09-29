"""
Urban Watch — Device Manager

Detects and selects the best available compute device.

Priority: CUDA → MPS (Apple Silicon) → CPU

Rules:
- Never hardcode device="cpu"
- Never silently fall back without logging
- Always log the selected device at startup
- Always expose device in API responses
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import torch

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    CUDA = "cuda"
    MPS = "mps"
    CPU = "cpu"


@dataclass(frozen=True)
class DeviceInfo:
    """Complete information about the selected compute device."""

    device_type: DeviceType
    device_str: str          # e.g. "cuda:0", "mps", "cpu"
    torch_version: str
    is_available: bool
    cuda_available: bool
    mps_available: bool
    device_name: str | None  # GPU name if available


def detect_device() -> DeviceInfo:
    """
    Detect the best available compute device.

    Returns a DeviceInfo with the selected device and full context.
    Never falls back silently — always logs what happened.
    """
    cuda_available = torch.cuda.is_available()
    mps_available = torch.backends.mps.is_available()

    if cuda_available:
        device_type = DeviceType.CUDA
        device_str = "cuda:0"
        try:
            device_name = torch.cuda.get_device_name(0)
        except Exception:
            device_name = "CUDA device (name unavailable)"
        logger.info("DEVICE: cuda — %s", device_name)

    elif mps_available:
        device_type = DeviceType.MPS
        device_str = "mps"
        device_name = "Apple Silicon MPS"
        logger.info("DEVICE: mps — Apple Silicon GPU acceleration")

    else:
        device_type = DeviceType.CPU
        device_str = "cpu"
        device_name = "CPU (no hardware accelerator available)"
        logger.warning(
            "DEVICE: cpu — no CUDA or MPS found. "
            "Inference will be significantly slower."
        )

    info = DeviceInfo(
        device_type=device_type,
        device_str=device_str,
        torch_version=torch.__version__,
        is_available=True,
        cuda_available=cuda_available,
        mps_available=mps_available,
        device_name=device_name,
    )

    logger.info(
        "Device selection complete: %s (CUDA=%s, MPS=%s, PyTorch=%s)",
        device_str,
        cuda_available,
        mps_available,
        torch.__version__,
    )
    return info


def get_torch_device(device_info: DeviceInfo | None = None) -> torch.device:
    """
    Return a torch.device object for use in model inference.

    If device_info is provided, uses it.
    Otherwise, re-detects the device (useful for testing).
    """
    if device_info is None:
        device_info = detect_device()
    return torch.device(device_info.device_str)


# Module-level singleton — initialized on first import.
# This ensures all components use the same device selection.
_DEVICE_INFO: DeviceInfo | None = None


def get_device_info() -> DeviceInfo:
    """Return the cached device info, detecting once on first call."""
    global _DEVICE_INFO
    if _DEVICE_INFO is None:
        _DEVICE_INFO = detect_device()
    return _DEVICE_INFO


def reset_device_cache() -> None:
    """Reset device cache. Useful in tests."""
    global _DEVICE_INFO
    _DEVICE_INFO = None
