"""
Urban Watch — Model Benchmarking Framework

Benchmarks candidate models on real test videos.

RULES:
1. If test videos are missing → report BENCHMARK NOT RUN — do NOT fabricate
2. Measure actual latency, FPS, detection counts — never estimate
3. Sweep: confidence (0.20, 0.25, 0.30, 0.40, 0.50)
4. Sweep: imgsz (320, 416, 512, 640)
5. Sweep: batch size (1, 2, 4) — only if MPS supports it
6. Record everything in structured JSON
7. Select model based on quality, not raw speed

Run:
    cd backend
    python -m ai.benchmarking.benchmark_models
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Ensure backend is in Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import psutil
import torch
import ultralytics

from ai.common.config import (
    MODEL_CANDIDATES,
    CONFIDENCE_SWEEP,
    IMGSZ_SWEEP,
    BATCH_SWEEP,
    INTERVAL_SWEEP,
)
from ai.common.device import get_device_info
from ai.common.timing import FrameTimer, timer, TimingStats
from ai.detection.classes import PHASE1_REQUIRED_CLASSES, get_phase1_class_ids
from ai.detection.model_loader import inspect_model
from video.reader import read_video_info, iter_frames, VideoReadError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")

# Test video paths (relative to project root)
TEST_VIDEO_PATHS = [
    "backend/video/test_data/traffic_test.mp4",
    "backend/video/test_data/road_test.mp4",
]

# Benchmark frame limit per run (keep it manageable)
BENCHMARK_FRAME_LIMIT = 100


@dataclass
class SingleRunResult:
    """Result of a single benchmark run (one model × one config)."""

    model: str
    device: str
    imgsz: int
    confidence: float
    frame_count: int
    total_detections: int
    avg_inference_ms: float
    min_inference_ms: float
    max_inference_ms: float
    fps: float
    memory_mb: float | None
    notes: str = ""
    error: str | None = None


@dataclass
class ModelBenchmarkResult:
    """All benchmark runs for a single model."""

    model: str
    device: str
    accepted: bool
    rejection_reason: str | None
    inspection: dict
    runs: list[SingleRunResult] = field(default_factory=list)
    recommended_imgsz: int | None = None
    recommended_confidence: float | None = None
    overall_notes: str = ""


def get_memory_usage_mb() -> float | None:
    """Return current process RSS memory in MB."""
    try:
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def run_inference_benchmark(
    model,
    video_path: str,
    device: str,
    imgsz: int,
    confidence: float,
    class_filter: list[int],
    frame_limit: int = BENCHMARK_FRAME_LIMIT,
) -> SingleRunResult:
    """
    Run inference on video frames and measure actual latency.

    Returns
    -------
    SingleRunResult with measured values (never fabricated).
    """
    inference_times: list[float] = []
    total_detections = 0
    frames_processed = 0

    mem_before = get_memory_usage_mb()

    for frame_index, timestamp, frame in iter_frames(video_path, interval=1):
        if frames_processed >= frame_limit:
            break

        with timer() as t:
            results = model.predict(
                source=frame,
                imgsz=imgsz,
                conf=confidence,
                iou=0.45,
                classes=class_filter,
                device=device,
                verbose=False,
                stream=False,
            )
        inference_ms = t[0]
        inference_times.append(inference_ms)

        # Count detections
        for result in results:
            if result.boxes is not None:
                total_detections += len(result.boxes)

        frames_processed += 1

    mem_after = get_memory_usage_mb()
    memory_delta = (
        (mem_after - mem_before)
        if mem_before is not None and mem_after is not None
        else None
    )

    if not inference_times:
        return SingleRunResult(
            model=str(model.model),
            device=device,
            imgsz=imgsz,
            confidence=confidence,
            frame_count=0,
            total_detections=0,
            avg_inference_ms=0.0,
            min_inference_ms=0.0,
            max_inference_ms=0.0,
            fps=0.0,
            memory_mb=memory_delta,
            error="No frames processed",
        )

    avg_ms = sum(inference_times) / len(inference_times)
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0

    return SingleRunResult(
        model=getattr(model, "ckpt_path", "unknown"),
        device=device,
        imgsz=imgsz,
        confidence=confidence,
        frame_count=frames_processed,
        total_detections=total_detections,
        avg_inference_ms=round(avg_ms, 3),
        min_inference_ms=round(min(inference_times), 3),
        max_inference_ms=round(max(inference_times), 3),
        fps=round(fps, 2),
        memory_mb=round(memory_delta, 2) if memory_delta is not None else None,
    )


def benchmark_all(
    candidates: list[dict] | None = None,
    test_video_paths: list[str] | None = None,
    results_dir: str = "results",
) -> list[ModelBenchmarkResult]:
    """
    Run full benchmark across all accepted model candidates.

    Results are saved to results/benchmark_report.json.
    """
    from ultralytics import YOLO

    if candidates is None:
        candidates = MODEL_CANDIDATES
    if test_video_paths is None:
        test_video_paths = TEST_VIDEO_PATHS

    device_info = get_device_info()
    device = device_info.device_str

    print("\n" + "=" * 70)
    print("URBAN WATCH — MODEL BENCHMARK")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Device: {device}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Ultralytics: {ultralytics.__version__}")
    print("=" * 70 + "\n")

    # -------------------------------------------------------------------------
    # Check test videos
    # -------------------------------------------------------------------------
    available_videos: list[str] = []
    missing_videos: list[str] = []

    for vpath in test_video_paths:
        abs_path = os.path.abspath(vpath)
        if os.path.exists(abs_path):
            try:
                info = read_video_info(abs_path)
                print(f"  ✓ Test video: {vpath}")
                print(f"    {info.width}x{info.height} @ {info.fps:.1f}fps, {info.frame_count} frames, {info.duration_seconds:.1f}s")
                available_videos.append(abs_path)
            except VideoReadError as exc:
                print(f"  ✗ Cannot read {vpath}: {exc}")
                missing_videos.append(vpath)
        else:
            print(f"  ✗ MISSING: {vpath}")
            missing_videos.append(vpath)

    if not available_videos:
        print("\n" + "!" * 70)
        print("BENCHMARK NOT RUN — TEST VIDEOS MISSING")
        print("Please place test videos at:")
        for vpath in test_video_paths:
            print(f"  {os.path.abspath(vpath)}")
        print("!" * 70 + "\n")

        # Still inspect models and return skeleton results
        model_results = []
        for candidate in candidates:
            inspection = inspect_model(candidate["pt_file"])
            model_results.append(ModelBenchmarkResult(
                model=candidate["pt_file"],
                device=device,
                accepted=inspection.accepted,
                rejection_reason=inspection.rejection_reason,
                inspection=inspection.model_dump(mode="json"),
                runs=[],
                overall_notes="BENCHMARK NOT RUN — TEST VIDEO MISSING",
            ))
        _save_report(model_results, results_dir)
        return model_results

    # -------------------------------------------------------------------------
    # Inspect and filter accepted models
    # -------------------------------------------------------------------------
    all_model_results: list[ModelBenchmarkResult] = []

    for candidate in candidates:
        pt_file = candidate["pt_file"]
        print(f"\n{'='*60}")
        print(f"Candidate: {pt_file} ({candidate['family']})")
        print("="*60)

        # Inspect
        inspection = inspect_model(pt_file)

        if not inspection.accepted:
            print(f"  REJECTED: {inspection.rejection_reason}")
            all_model_results.append(ModelBenchmarkResult(
                model=pt_file,
                device=device,
                accepted=False,
                rejection_reason=inspection.rejection_reason,
                inspection=inspection.model_dump(mode="json"),
                runs=[],
                overall_notes=f"Rejected during inspection: {inspection.rejection_reason}",
            ))
            continue

        print(f"  ✓ Accepted: {inspection.num_classes} classes, {inspection.num_parameters or 'unknown'} params")

        # Load model
        try:
            model = YOLO(pt_file)
            model.to(device)
            class_filter = get_phase1_class_ids(model.names)
        except Exception as exc:
            reason = f"Model load error: {exc}"
            print(f"  ✗ {reason}")
            all_model_results.append(ModelBenchmarkResult(
                model=pt_file,
                device=device,
                accepted=False,
                rejection_reason=reason,
                inspection=inspection.model_dump(mode="json"),
                overall_notes=reason,
            ))
            continue

        model_result = ModelBenchmarkResult(
            model=pt_file,
            device=device,
            accepted=True,
            rejection_reason=None,
            inspection=inspection.model_dump(mode="json"),
        )

        # Use first available video for benchmarking
        video_path = available_videos[0]

        # -------------------------------------------------------------------------
        # Sweep: imgsz (at default confidence)
        # -------------------------------------------------------------------------
        print(f"\n  IMGSZ sweep (confidence=0.25):")
        for imgsz in IMGSZ_SWEEP:
            print(f"    imgsz={imgsz}...", end="", flush=True)
            try:
                run = run_inference_benchmark(
                    model=model,
                    video_path=video_path,
                    device=device,
                    imgsz=imgsz,
                    confidence=0.25,
                    class_filter=class_filter,
                )
                print(f" {run.avg_inference_ms:.1f}ms avg, {run.fps:.1f}fps, {run.total_detections} dets")
                model_result.runs.append(run)
            except Exception as exc:
                print(f" ERROR: {exc}")

        # -------------------------------------------------------------------------
        # Sweep: confidence (at imgsz=640)
        # -------------------------------------------------------------------------
        print(f"\n  Confidence sweep (imgsz=640):")
        for conf in CONFIDENCE_SWEEP:
            print(f"    conf={conf}...", end="", flush=True)
            try:
                run = run_inference_benchmark(
                    model=model,
                    video_path=video_path,
                    device=device,
                    imgsz=640,
                    confidence=conf,
                    class_filter=class_filter,
                )
                print(f" {run.avg_inference_ms:.1f}ms avg, {run.fps:.1f}fps, {run.total_detections} dets")
                model_result.runs.append(run)
            except Exception as exc:
                print(f" ERROR: {exc}")

        # -------------------------------------------------------------------------
        # Sweep: batch size (at imgsz=640, conf=0.25) — MPS only if beneficial
        # -------------------------------------------------------------------------
        print(f"\n  Batch sweep (imgsz=640, conf=0.25):")
        print("    NOTE: Batch sweep uses predict() on batches of static frames.")
        for batch_size in BATCH_SWEEP:
            if batch_size == 1:
                continue  # Already covered in sweeps above
            print(f"    batch={batch_size}...", end="", flush=True)
            try:
                # Collect frames for batch
                batch_frames = []
                for _, _, f in iter_frames(video_path, interval=1):
                    batch_frames.append(f)
                    if len(batch_frames) >= min(batch_size, 10):
                        break

                batch_times = []
                for j in range(0, len(batch_frames), batch_size):
                    batch = batch_frames[j:j+batch_size]
                    with timer() as t:
                        model.predict(
                            source=batch,
                            imgsz=640,
                            conf=0.25,
                            iou=0.45,
                            classes=class_filter,
                            device=device,
                            verbose=False,
                        )
                    batch_times.append(t[0])

                if batch_times:
                    avg = sum(batch_times) / len(batch_times)
                    fps = batch_size * 1000.0 / avg if avg > 0 else 0.0
                    print(f" {avg:.1f}ms per batch, ~{fps:.1f}fps effective")
                else:
                    print(" no frames")
            except Exception as exc:
                print(f" ERROR: {exc}")

        all_model_results.append(model_result)

    # -------------------------------------------------------------------------
    # Save full report
    # -------------------------------------------------------------------------
    _save_report(all_model_results, results_dir)

    # Print final table
    _print_summary_table(all_model_results)

    return all_model_results


def _save_report(results: list[ModelBenchmarkResult], results_dir: str) -> None:
    """Save benchmark results as JSON."""
    os.makedirs(results_dir, exist_ok=True)
    report_path = os.path.join(results_dir, "benchmark_report.json")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": [
            {
                "model": r.model,
                "device": r.device,
                "accepted": r.accepted,
                "rejection_reason": r.rejection_reason,
                "runs": [asdict(run) for run in r.runs],
                "notes": r.overall_notes,
            }
            for r in results
        ],
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nBenchmark report saved: {report_path}")


def _print_summary_table(results: list[ModelBenchmarkResult]) -> None:
    """Print a human-readable summary table."""
    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)
    print(f"{'Model':<15} {'Device':<6} {'imgsz':<6} {'Conf':<6} {'FPS':<8} {'Avg ms':<10} {'Dets'}")
    print("-"*70)

    for mr in results:
        if not mr.accepted or not mr.runs:
            status = mr.rejection_reason or "NO RUNS"
            print(f"{mr.model:<15} {'—':<6} {'—':<6} {'—':<6} {'—':<8} {'—':<10} {status}")
            continue

        for run in mr.runs:
            if run.error:
                continue
            print(
                f"{mr.model:<15} {run.device:<6} {run.imgsz:<6} "
                f"{run.confidence:<6} {run.fps:<8.2f} "
                f"{run.avg_inference_ms:<10.1f} {run.total_detections}"
            )

    print("="*70)
    print("NOTE: mAP/precision/recall NOT MEASURED — no ground-truth dataset")
    print("="*70 + "\n")


if __name__ == "__main__":
    abs_results = os.path.abspath("results")
    benchmark_all(results_dir=abs_results)
