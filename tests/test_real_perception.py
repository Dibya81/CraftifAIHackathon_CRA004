"""Unit and integration tests for real perception tools, dataset splits, and labeling."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from sentinel.adapters.baseline_detector import BaselineONNXDetector
from tools.label_clip import parse_interval_spec, save_labels, validate_intervals
from tools.prepare_dataset import prepare_dataset
from tools.validate_dataset import check_tuning_permission, validate_split_integrity


def test_baseline_detector_letterbox():
    detector = BaselineONNXDetector(model_path="models/baseline/detector.onnx")
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    padded, scale, (pad_x, pad_y) = detector.letterbox(img, new_shape=(640, 640))

    assert padded.shape == (640, 640, 3)
    assert scale == 1.0
    assert pad_x == 0
    assert pad_y == 80  # (640 - 480) // 2


def test_baseline_detector_nms():
    detector = BaselineONNXDetector(model_path="models/baseline/detector.onnx")
    # Two overlapping boxes
    boxes = [
        [100.0, 100.0, 200.0, 200.0],
        [105.0, 105.0, 202.0, 201.0],
    ]
    scores = [0.9, 0.8]
    keep = detector._nms(boxes, scores, iou_threshold=0.5)
    assert keep == [0]


def test_baseline_detector_class_mapping():
    class_map = {"0": "person", "1": "helmet", "2": "vest"}
    detector = BaselineONNXDetector(
        model_path="models/baseline/detector.onnx",
        class_map=class_map,
    )
    assert detector.map_class(0) == "person"
    assert detector.map_class(1) == "helmet"
    assert detector.map_class(2) == "vest"


def test_label_clip_parse_and_validate():
    # Valid interval
    v = parse_interval_spec("NO_HELMET:2.0:5.0:worker-1:press-area", max_duration=10.0)
    assert v["rule_type"] == "NO_HELMET"
    assert v["person"] == "worker-1"
    assert v["start_s"] == 2.0
    assert v["end_s"] == 5.0
    assert v["zone"] == "press-area"

    # Start >= end should raise ValueError
    with pytest.raises(ValueError, match="strictly greater"):
        parse_interval_spec("NO_HELMET:5.0:2.0:worker-1:press-area")

    # Exceeding duration should raise ValueError
    with pytest.raises(ValueError, match="exceeds clip duration"):
        parse_interval_spec("NO_HELMET:12.0:15.0:worker-1:press-area", max_duration=10.0)


def test_label_clip_overlap_validation():
    # Overlapping intervals for the same person and rule type must raise ValueError
    intervals = [
        {"person": "worker-1", "rule_type": "NO_HELMET", "start_s": 2.0, "end_s": 6.0},
        {"person": "worker-1", "rule_type": "NO_HELMET", "start_s": 4.0, "end_s": 8.0},
    ]
    with pytest.raises(ValueError, match="Overlapping interval"):
        validate_intervals(intervals, max_duration=20.0)


def test_label_clip_undo(tmp_path: Path):
    out_file = tmp_path / "test_labels.json"
    clip_info = {"clip": "test.mp4", "duration_s": 10.0, "fps": 25.0, "frame_count": 250}
    violations = [
        {"person": "w1", "rule_type": "NO_HELMET", "start_s": 1.0, "end_s": 3.0},
        {"person": "w1", "rule_type": "NO_HELMET", "start_s": 4.0, "end_s": 6.0},
    ]
    save_labels(out_file, clip_info, violations)

    # Pop last interval via --undo CLI
    proc = subprocess.run(
        [sys.executable, "tools/label_clip.py", "--out", str(out_file), "--undo"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Undid interval" in proc.stdout

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["violations"]) == 1
    assert data["violations"][0]["end_s"] == 3.0


def test_dataset_split_generation_and_validation(tmp_path: Path):
    clips_dir = tmp_path / "clips"
    labels_dir = tmp_path / "labels"
    out_dir = tmp_path / "dataset"
    clips_dir.mkdir()
    labels_dir.mkdir()

    # Create dummy video clip
    clip_path = clips_dir / "clip_a.mp4"
    import cv2
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(clip_path), fourcc, 25.0, (320, 240))
    for _ in range(30):
        vw.write(np.zeros((240, 320, 3), dtype=np.uint8))
    vw.release()

    labels_file = labels_dir / "clip_a.json"
    labels_file.write_text(
        json.dumps({
            "clip": "clip_a.mp4",
            "violations": [{"person": "w1", "type": "NO_HELMET", "start_s": 0.2, "end_s": 0.8}],
        }),
        encoding="utf-8",
    )

    manifest = prepare_dataset(
        clips_dir=clips_dir,
        labels_dir=labels_dir,
        output_dir=out_dir,
        stride=5,
        dev_ratio=0.5,
    )
    assert manifest["split_sha256"]
    assert (out_dir / "dataset_manifest.json").exists()

    # Verify manifest integrity
    valid, errors = validate_split_integrity(out_dir / "dataset_manifest.json")
    assert valid, f"Validation errors: {errors}"


def test_validate_dataset_refuses_tuning_on_test_split():
    with pytest.raises(SystemExit):
        check_tuning_permission(task="tune", split="test")

    with pytest.raises(SystemExit):
        check_tuning_permission(task="train", split="test")

    # Allowed on dev split
    check_tuning_permission(task="tune", split="dev")
    check_tuning_permission(task="eval", split="test")
