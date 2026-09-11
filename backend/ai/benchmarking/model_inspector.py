"""
Urban Watch — Model Inspector

Static inspection of model candidates.
Loads each candidate, extracts metadata, validates classes.
Does NOT run inference — only inspects model structure.

Run standalone:
    cd backend
    python -m ai.benchmarking.model_inspector
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import ultralytics
import torch

from ai.common.config import MODEL_CANDIDATES
from ai.common.schemas import ModelInspectionResult
from ai.detection.model_loader import inspect_model, ULTRALYTICS_LICENSE, ULTRALYTICS_SOURCE
from ai.detection.classes import PHASE1_REQUIRED_CLASSES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("model_inspector")


def inspect_all_candidates(
    candidates: list[dict] | None = None,
    save_report: bool = True,
) -> list[ModelInspectionResult]:
    """
    Inspect all model candidates and return their inspection results.

    Parameters
    ----------
    candidates : list[dict] or None
        Model candidates from config. If None, uses MODEL_CANDIDATES.
    save_report : bool
        Whether to save the inspection report as JSON.

    Returns
    -------
    list[ModelInspectionResult]
    """
    if candidates is None:
        candidates = MODEL_CANDIDATES

    results: list[ModelInspectionResult] = []

    print("\n" + "=" * 70)
    print("URBAN WATCH — MODEL INSPECTION")
    print(f"Ultralytics: {ultralytics.__version__}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Candidates: {len(candidates)}")
    print(f"Required classes: {sorted(PHASE1_REQUIRED_CLASSES)}")
    print("=" * 70 + "\n")

    for i, candidate in enumerate(candidates):
        pt_file = candidate["pt_file"]
        print(f"[{i+1}/{len(candidates)}] Inspecting: {pt_file}")
        print(f"  Priority: {candidate['priority']}")
        print(f"  Family: {candidate['family']}")
        print(f"  Description: {candidate['description']}")

        result = inspect_model(pt_file)

        print(f"  Status: {'✓ ACCEPTED' if result.accepted else '✗ REJECTED'}")
        print(f"  Task: {result.task or 'UNKNOWN'}")
        print(f"  Classes: {result.num_classes}")
        if result.num_parameters:
            print(f"  Parameters: {result.num_parameters:,}")
        if result.model_size_mb:
            print(f"  Size: {result.model_size_mb:.1f} MB")
        if result.load_time_ms:
            print(f"  Load time: {result.load_time_ms:.1f} ms")
        if result.rejection_reason:
            print(f"  Rejection reason: {result.rejection_reason}")
        if result.missing_classes:
            print(f"  Missing classes: {result.missing_classes}")
        print(f"  License: {result.license or 'UNKNOWN'}")
        print()

        results.append(result)

    # Summary
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]

    print("=" * 70)
    print(f"INSPECTION SUMMARY")
    print(f"  Accepted: {len(accepted)}")
    print(f"  Rejected: {len(rejected)}")
    print()

    if accepted:
        print("ACCEPTED MODELS:")
        for r in accepted:
            print(f"  ✓ {r.pt_file} ({r.num_classes} classes, {r.num_parameters or 'unknown'} params)")

    if rejected:
        print("\nREJECTED MODELS:")
        for r in rejected:
            print(f"  ✗ {r.pt_file}: {r.rejection_reason}")

    print("=" * 70 + "\n")

    # Save report
    if save_report:
        report_path = os.path.join(
            Path(__file__).parent.parent.parent,
            "results",
            "model_inspection_report.json",
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(
                [r.model_dump() for r in results],
                f,
                indent=2,
                default=str,
            )
        print(f"Report saved: {report_path}")

    return results


if __name__ == "__main__":
    inspect_all_candidates()
