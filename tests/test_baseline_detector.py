"""Tests for Baseline CPU ONNX detector."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sentinel.adapters.baseline_detector import BaselineONNXDetector

MODEL_PATH = Path("models/baseline/detector.onnx")


def test_baseline_detector_skips_when_weights_absent():
    """Verify detector reports ready=False and skips cleanly when weights are not downloaded."""
    detector = BaselineONNXDetector(model_path="models/baseline/nonexistent.onnx")
    assert detector.is_ready is False


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="Baseline ONNX weights not downloaded (run scripts/fetch_baseline_model.sh)",
)
def test_baseline_detector_inference_on_synthetic_frame():
    """Verify baseline detector runs inference and produces canonical FrameMeta."""
    detector = BaselineONNXDetector(model_path=MODEL_PATH)
    assert detector.is_ready is True

    # 1080p synthetic image
    frame = np.full((1080, 1920, 3), 120, dtype=np.uint8)
    meta = detector.detect(frame, frame_id=1, timestamp=0.04)

    assert meta.frame_id == 1
    assert meta.frame.width == 1920
    assert meta.frame.height == 1080
    assert isinstance(meta.detections, list)


@pytest.mark.real
@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="Baseline ONNX weights not downloaded (run scripts/fetch_baseline_model.sh)",
)
def test_baseline_detector_on_real_fixture_clip():
    """Verify baseline detector processes frames from a committed real video clip under 2 MB."""
    import cv2

    clip_path = Path("tests/fixtures/real_sample_clip.mp4")
    assert clip_path.exists(), "tests/fixtures/real_sample_clip.mp4 must exist"
    assert clip_path.stat().st_size < 2 * 1024 * 1024, "Real clip fixture must be under 2 MB"

    detector = BaselineONNXDetector(model_path=MODEL_PATH)
    assert detector.is_ready is True

    cap = cv2.VideoCapture(str(clip_path))
    assert cap.isOpened(), f"Failed to open video clip {clip_path}"

    frames_processed = 0
    try:
        while frames_processed < 5:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            meta = detector.detect(
                frame, frame_id=frames_processed + 1, timestamp=frames_processed * 0.04
            )
            assert meta.frame_id == frames_processed + 1
            assert meta.frame.width == frame.shape[1]
            assert meta.frame.height == frame.shape[0]
            frames_processed += 1
    finally:
        cap.release()

    assert frames_processed > 0, "Should have processed at least 1 frame from real clip"
