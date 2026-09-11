"""Tests for model loader — class validation, inspection."""

from __future__ import annotations

import pytest

from ai.detection.classes import (
    validate_required_classes,
    get_vehicle_class_ids,
    get_phase1_class_ids,
    is_vehicle_class,
    PHASE1_REQUIRED_CLASSES,
    VEHICLE_CLASSES,
)


# Simulated model.names for a standard COCO model
COCO_MODEL_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    # ... additional COCO classes
}

# Model that is missing 'bus' and 'truck'
INCOMPLETE_MODEL_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
}


def test_validate_required_classes_all_present():
    """A complete COCO model should pass validation."""
    ok, missing = validate_required_classes(COCO_MODEL_NAMES)
    assert ok is True
    assert missing == []


def test_validate_required_classes_missing():
    """Model missing 'bus' and 'truck' must fail validation."""
    ok, missing = validate_required_classes(INCOMPLETE_MODEL_NAMES)
    assert ok is False
    assert "bus" in missing
    assert "truck" in missing


def test_get_vehicle_class_ids():
    """Vehicle class IDs must be extracted from model.names."""
    ids = get_vehicle_class_ids(COCO_MODEL_NAMES)
    # Should include car=2, motorcycle=3, bus=5, truck=7, bicycle=1
    assert 2 in ids  # car
    assert 3 in ids  # motorcycle
    assert 5 in ids  # bus
    assert 7 in ids  # truck
    assert 1 in ids  # bicycle
    # Should NOT include person=0
    assert 0 not in ids


def test_get_phase1_class_ids_includes_person():
    """Phase 1 class IDs include person (for pedestrian tracking)."""
    ids = get_phase1_class_ids(COCO_MODEL_NAMES)
    assert 0 in ids  # person


def test_is_vehicle_class_positive():
    """Vehicle class names return True."""
    for cls in ["car", "motorcycle", "bus", "truck", "bicycle"]:
        assert is_vehicle_class(cls) is True


def test_is_vehicle_class_negative():
    """Non-vehicle classes return False."""
    for cls in ["person", "airplane", "boat", "train", "cat", "pothole"]:
        assert is_vehicle_class(cls) is False


def test_vehicle_classes_subset_of_phase1():
    """VEHICLE_CLASSES must be a subset of PHASE1_REQUIRED_CLASSES (minus person)."""
    # All vehicle classes should be in the required set
    assert VEHICLE_CLASSES.issubset(PHASE1_REQUIRED_CLASSES)


def test_phase1_includes_person():
    """Phase 1 required classes must include 'person'."""
    assert "person" in PHASE1_REQUIRED_CLASSES


def test_no_fake_class_mapping():
    """Verifies that classes like 'pothole' are NOT in PHASE1_REQUIRED_CLASSES."""
    forbidden = {"pothole", "helmet", "nohelmet", "waterlogging", "road_damage"}
    assert len(forbidden.intersection(PHASE1_REQUIRED_CLASSES)) == 0
