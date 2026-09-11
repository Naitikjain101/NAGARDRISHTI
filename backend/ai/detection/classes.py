"""
Urban Watch — Phase 1 Required Class Definitions

These are the COCO classes required for Phase 1 traffic detection.

IMPORTANT:
- These class IDs are for standard COCO-pretrained models.
- Do NOT assume a model has these classes — always verify via model.names.
- VEHICLE_CLASSES is the subset used for vehicle counting.
- ALL_PHASE1_CLASSES includes persons (for pedestrian density context).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# COCO class IDs for Phase 1 required classes
# ---------------------------------------------------------------------------

# Map: COCO class ID → class name
# Source: COCO dataset official class list
COCO_CLASS_NAMES: dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic light",
    10: "fire hydrant",
    11: "stop sign",
    12: "parking meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports ball",
    33: "kite",
    34: "baseball bat",
    35: "baseball glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis racket",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "sandwich",
}

# ---------------------------------------------------------------------------
# Phase 1 required class names
# ---------------------------------------------------------------------------

# All classes required for Phase 1 detection
PHASE1_REQUIRED_CLASSES: set[str] = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
}

# Vehicle classes used for vehicle counting and traffic density.
# Does NOT include "person" — persons are tracked separately.
VEHICLE_CLASSES: set[str] = {
    "car",
    "motorcycle",
    "bus",
    "truck",
    "bicycle",
}

# All classes detected in Phase 1 (vehicles + person for context)
ALL_PHASE1_CLASSES: set[str] = PHASE1_REQUIRED_CLASSES


# ---------------------------------------------------------------------------
# Class filter helpers
# ---------------------------------------------------------------------------

def get_vehicle_class_ids(model_names: dict[int, str]) -> list[int]:
    """
    Return COCO class IDs that correspond to VEHICLE_CLASSES in a given model.

    Only returns IDs that are ACTUALLY in the model's class list.
    Never fabricates class IDs.
    """
    return [
        cid
        for cid, name in model_names.items()
        if name in VEHICLE_CLASSES
    ]


def get_phase1_class_ids(model_names: dict[int, str]) -> list[int]:
    """
    Return class IDs for all Phase 1 required classes in a given model.
    """
    return [
        cid
        for cid, name in model_names.items()
        if name in PHASE1_REQUIRED_CLASSES
    ]


def validate_required_classes(
    model_names: dict[int, str],
    required: set[str] | None = None,
) -> tuple[bool, list[str]]:
    """
    Check if a model contains all required classes.

    Returns:
        (all_present: bool, missing_classes: list[str])
    """
    if required is None:
        required = PHASE1_REQUIRED_CLASSES

    found = set(model_names.values())
    missing = [cls for cls in sorted(required) if cls not in found]
    return (len(missing) == 0), missing


def is_vehicle_class(class_name: str) -> bool:
    """Return True if the class name is a vehicle class."""
    return class_name in VEHICLE_CLASSES
