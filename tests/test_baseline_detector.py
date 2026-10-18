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
