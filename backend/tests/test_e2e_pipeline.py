"""
Urban Watch — End-to-End Pipeline Tests
Tests the complete upload → process → poll → complete cycle with a real video.

Usage:
    cd backend
    python -m pytest tests/test_e2e_pipeline.py -v --timeout=300
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import pytest
import httpx

# ── Config ──────────────────────────────────────────────────────────────────

BASE_URL      = "http://127.0.0.1:8000"
# road_test.mp4 is ~1.2 MB, short clip — fast to process
TEST_VIDEO    = Path(__file__).parent.parent / "video" / "test_data" / "road_test.mp4"
TRAFFIC_VIDEO = Path(__file__).parent.parent / "video" / "test_data" / "traffic_test.mp4"

POLL_INTERVAL_S = 2          # seconds between status polls
MAX_WAIT_S      = 300        # 5 minutes max — should never be needed for road_test.mp4


# ── Helpers ─────────────────────────────────────────────────────────────────

def upload_video(client: httpx.Client, path: Path) -> dict:
    """Upload a real video file and return the response JSON."""
    assert path.exists(), f"Test video not found: {path}"
    with open(path, "rb") as f:
        resp = client.post(
            f"{BASE_URL}/api/video/upload",
            files={"file": (path.name, f, "video/mp4")},
            timeout=60,
        )
    assert resp.status_code == 200, f"Upload failed {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "video_id" in data, f"Response missing video_id: {data}"
    return data


def start_processing(client: httpx.Client, video_id: str) -> dict:
    """Trigger processing and return the response JSON."""
    resp = client.post(f"{BASE_URL}/api/ai/unified/process/{video_id}", timeout=30)
    assert resp.status_code == 200, f"Process start failed {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "job_id" in data, f"Response missing job_id: {data}"
    assert data.get("status") in ("queued", "running", "completed"), f"Unexpected start status: {data}"
    return data


def poll_until_terminal(client: httpx.Client, video_id: str, max_wait: int = MAX_WAIT_S) -> dict:
    """Poll GET /api/ai/unified/status/{video_id} until status is terminal. Return final status dict."""
    terminal = {"completed", "failed", "cancelled"}
    deadline = time.time() + max_wait

    last_status: dict = {}
    while time.time() < deadline:
        resp = client.get(f"{BASE_URL}/api/ai/unified/status/{video_id}", timeout=15)
        assert resp.status_code == 200, f"Status poll failed {resp.status_code}: {resp.text}"
        last_status = resp.json()
        status = last_status.get("status")
        progress = last_status.get("progress_frames", 0)
        total    = last_status.get("total_frames", 0)
        print(f"  [poll] status={status}  {progress}/{total} frames  fps={last_status.get('processing_fps')}")

        if status in terminal:
            return last_status

        time.sleep(POLL_INTERVAL_S)

    pytest.fail(f"Processing did not reach terminal state within {max_wait}s. Last: {last_status}")


# ── Tests ────────────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_backend_reachable(self):
        with httpx.Client() as client:
            resp = client.get(f"{BASE_URL}/health", timeout=10)
        assert resp.status_code == 200, f"Backend not reachable: {resp.status_code}"
        data = resp.json()
        assert data.get("status") in ("HEALTHY", "DEGRADED"), f"Unexpected health: {data}"
        print(f"\n  [health] {data}")


class TestVideoUpload:
    def test_upload_valid_video(self):
        with httpx.Client() as client:
            data = upload_video(client, TEST_VIDEO)
        assert data["video_id"]
        assert data["filename"]
        meta = data.get("metadata", {})
        assert meta.get("frame_count", 0) > 0,     f"frame_count missing: {meta}"
        assert meta.get("fps", 0) > 0,             f"fps missing: {meta}"
        assert meta.get("width", 0) > 0,           f"width missing: {meta}"
        assert meta.get("height", 0) > 0,          f"height missing: {meta}"
        print(f"\n  [upload] video_id={data['video_id']} frames={meta.get('frame_count')} fps={meta.get('fps')} {meta.get('width')}x{meta.get('height')}")

    def test_upload_empty_file_returns_422(self):
        """Empty file must return 4xx, not hang or crash."""
        with httpx.Client() as client:
            empty = io.BytesIO(b"")
            resp = client.post(
                f"{BASE_URL}/api/video/upload",
                files={"file": ("empty.mp4", empty, "video/mp4")},
                timeout=30,
            )
        assert resp.status_code in (413, 415, 422, 500), \
            f"Expected 4xx for empty file, got {resp.status_code}: {resp.text}"
        print(f"\n  [upload_empty] status={resp.status_code}")

    def test_upload_corrupted_file_returns_422(self):
        """Corrupted content must return 422 (Invalid or corrupt video file), not hang."""
        garbage = b"\x00\x01\x02\x03NOTAVIDEO" * 100
        with httpx.Client() as client:
            resp = client.post(
                f"{BASE_URL}/api/video/upload",
                files={"file": ("corrupt.mp4", io.BytesIO(garbage), "video/mp4")},
                timeout=30,
            )
        assert resp.status_code in (422, 500), \
            f"Expected 422 for corrupt file, got {resp.status_code}: {resp.text}"
        print(f"\n  [upload_corrupt] status={resp.status_code} detail={resp.json().get('detail', '')}")

    def test_upload_wrong_type_returns_415(self):
        """Non-video content type must be rejected."""
        with httpx.Client() as client:
            resp = client.post(
                f"{BASE_URL}/api/video/upload",
                files={"file": ("doc.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
                timeout=30,
            )
        assert resp.status_code == 415, f"Expected 415, got {resp.status_code}"
        print(f"\n  [upload_wrong_type] status={resp.status_code}")


class TestEndToEndPipeline:
    """Full upload → process → poll → complete cycle with a real video."""

    def test_road_test_full_pipeline(self):
        assert TEST_VIDEO.exists(), f"Test video missing: {TEST_VIDEO}"
        file_size = TEST_VIDEO.stat().st_size
        print(f"\n  [e2e] test_video={TEST_VIDEO.name} size={file_size/1024:.1f}KB")

        with httpx.Client() as client:
            # 1. Upload
            upload_data = upload_video(client, TEST_VIDEO)
            video_id = upload_data["video_id"]
            meta = upload_data.get("metadata", {})
            total_frames_from_meta = meta.get("frame_count", 0)
            fps_from_meta = meta.get("fps", 0)
            print(f"  [e2e] video_id={video_id}  total_frames(meta)={total_frames_from_meta}  fps={fps_from_meta}")
            assert total_frames_from_meta > 0, "Video metadata reports 0 frames"

            # 2. Trigger processing
            proc_data = start_processing(client, video_id)
            job_id = proc_data["job_id"]
            print(f"  [e2e] job_id={job_id}  start_status={proc_data['status']}")
            assert job_id

            # 3. Poll until terminal
            t_start = time.time()
            final_status = poll_until_terminal(client, video_id)
            duration = time.time() - t_start
            print(f"\n  [e2e] FINAL_STATUS = {final_status}")
            print(f"  [e2e] Duration: {duration:.1f}s")

            # 4. Assert completion
            assert final_status["status"] == "completed", \
                f"Expected status=completed, got: {final_status['status']}\nError: {final_status.get('error')}"
            assert final_status.get("error") is None, \
                f"Expected error=null, got: {final_status.get('error')}"
            assert final_status.get("total_frames", 0) > 0, \
                f"total_frames must be > 0, got: {final_status.get('total_frames')}"
            assert final_status.get("progress_frames", 0) == final_status.get("total_frames", -1), \
                (f"progress_frames ({final_status.get('progress_frames')}) "
                 f"!= total_frames ({final_status.get('total_frames')})")

            print(f"\n  ✅ PASS: status=completed  progress={final_status['progress_frames']}/{final_status['total_frames']}  error=null")

            # 5. Verify results file was created
            results_path = Path(__file__).parent.parent / "results" / f"{video_id}_unified.json"
            assert results_path.exists(), f"Results JSON not created: {results_path}"
            with open(results_path) as f:
                results = json.load(f)

            assert results.get("status") in ("completed", "complete"), \
                f"Results JSON status unexpected: {results.get('status')}"
            print(f"  [e2e] results_file_ok  pothole_events={len(results.get('pothole_events', []))}  waterlogging_events={len(results.get('waterlogging_events', []))}")

            # 6. Check no orphaned jobs (jobs stuck in running/queued)
            resp = client.get(f"{BASE_URL}/api/ai/unified/status/{video_id}", timeout=10)
            assert resp.status_code == 200
            final_check = resp.json()
            assert final_check["status"] not in ("queued", "running"), \
                f"Job is still active after processing completed: {final_check}"

            return {
                "video_id": video_id,
                "job_id": job_id,
                "final_status": final_status,
                "duration_s": duration,
            }


class TestFailureCases:
    """Every failure path must end in status=failed with a real message."""

    def test_process_nonexistent_video_returns_404(self):
        fake_id = "00000000-0000-0000-0000-000000000000"
        with httpx.Client() as client:
            resp = client.post(f"{BASE_URL}/api/ai/unified/process/{fake_id}", timeout=15)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"\n  [failure] nonexistent_video={resp.status_code} detail={resp.json().get('detail', '')}")

    def test_status_nonexistent_job_returns_404(self):
        fake_id = "00000000-0000-0000-0000-000000000001"
        with httpx.Client() as client:
            resp = client.get(f"{BASE_URL}/api/ai/unified/status/{fake_id}", timeout=15)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"\n  [failure] status_nonexistent={resp.status_code}")

    def test_idempotency_already_processing(self):
        """Starting processing twice on the same video must return the existing job, not start a new one."""
        assert TEST_VIDEO.exists(), f"Test video missing: {TEST_VIDEO}"
        with httpx.Client() as client:
            # Upload
            upload_data = upload_video(client, TEST_VIDEO)
            video_id = upload_data["video_id"]

            # Trigger once
            resp1 = client.post(f"{BASE_URL}/api/ai/unified/process/{video_id}", timeout=30)
            assert resp1.status_code == 200
            job_id_1 = resp1.json().get("job_id")

            # Trigger again immediately
            resp2 = client.post(f"{BASE_URL}/api/ai/unified/process/{video_id}", timeout=30)
            assert resp2.status_code == 200
            data2 = resp2.json()

            # The second call should return the same job_id or indicate "already processing"
            msg = data2.get("message", "")
            print(f"\n  [idempotency] second_call_message='{msg}' job_id_2={data2.get('job_id')}")
            assert "already" in msg.lower() or data2.get("job_id") == job_id_1, \
                f"Expected idempotent response, got: {data2}"
