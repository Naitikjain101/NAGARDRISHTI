"""Tests for device selection."""

from __future__ import annotations

import pytest


def test_device_detection_returns_device_info():
    from ai.common.device import detect_device, DeviceInfo
    info = detect_device()
    assert isinstance(info, DeviceInfo)
    assert info.device_str in ("cuda:0", "cuda", "mps", "cpu")


def test_device_str_is_valid():
    from ai.common.device import get_device_info
    info = get_device_info()
    # Must be one of the valid device types
    assert info.device_str in ("cuda:0", "cuda", "mps", "cpu")


def test_device_info_is_consistent():
    """Device info fields must be internally consistent."""
    from ai.common.device import detect_device, DeviceType
    info = detect_device()

    if info.device_type == DeviceType.CUDA:
        assert info.cuda_available
        assert "cuda" in info.device_str
    elif info.device_type == DeviceType.MPS:
        assert info.mps_available
        assert info.device_str == "mps"
    else:
        assert info.device_str == "cpu"


def test_device_exposes_torch_version():
    """Device info must include PyTorch version."""
    import torch
    from ai.common.device import get_device_info
    info = get_device_info()
    assert info.torch_version == torch.__version__


def test_mps_detection():
    """On Apple Silicon Mac, MPS must be available (test environment)."""
    import torch
    from ai.common.device import get_device_info
    info = get_device_info()
    # This test machine has MPS — verify it's detected
    if torch.backends.mps.is_available():
        assert info.mps_available
        # MPS should be selected over CPU (no CUDA)
        if not info.cuda_available:
            assert info.device_str == "mps"


def test_device_cache_is_singleton():
    """get_device_info() must return the same object on repeated calls."""
    from ai.common.device import get_device_info, reset_device_cache
    reset_device_cache()
    info1 = get_device_info()
    info2 = get_device_info()
    assert info1 is info2


def test_get_torch_device_returns_device():
    """get_torch_device() must return a valid torch.device."""
    import torch
    from ai.common.device import get_torch_device
    device = get_torch_device()
    assert isinstance(device, torch.device)
