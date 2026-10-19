"""Comprehensive unit, fuzz, property, and format-diagnosis tests for PipeGenAdapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.adapters.pipegen import JsonFileMetadataTailer, PipeGenAdapter
from sentinel.domain.models import FrameMeta


@pytest.mark.tc("TC-16")
def test_parse_fixture_sample():
    adapter = PipeGenAdapter()
    fixture_path = Path("tests/fixtures/pipegen_sample.json")
    assert fixture_path.exists()

    frame_meta = adapter.parse_payload(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(frame_meta, FrameMeta)
    assert frame_meta.camera_id == "cam-01"
    assert frame_meta.frame_id == 100
    assert frame_meta.ts == 1776435600.0
    assert frame_meta.frame is not None
    assert frame_meta.frame.width == 1920
    assert frame_meta.frame.height == 1080

    assert len(frame_meta.detections) == 3
    classes = [d.class_name for d in frame_meta.detections]
    assert classes == ["person", "helmet", "vest"]

    p = frame_meta.detections[0]
    assert p.track_id == 7
    assert p.conf == 0.94
    assert p.box.to_list() == [500.0, 300.0, 700.0, 800.0]


def test_numeric_class_mapping():
    adapter = PipeGenAdapter(
        class_map={"0": "person", "1": "helmet", "2": "no_helmet", "3": "vest"}
    )
    raw_payload = {
        "camera_id": "cam-test",
        "frame_id": 1,
        "ts": 10.0,
        "objects": [
            {"track_id": 1, "class_id": 0, "conf": 0.9, "bbox": [10, 10, 50, 100]},
            {"track_id": None, "class_id": 2, "conf": 0.85, "bbox": [15, 10, 45, 30]},
        ],
    }
    meta = adapter.parse_payload(raw_payload)
    assert len(meta.detections) == 2
    assert meta.detections[0].class_name == "person"
    assert meta.detections[1].class_name == "no_helmet"


def test_deepstream_array_schema_parsing():
    adapter = PipeGenAdapter(format_mode="auto")
    ds_payload = {
        "version": "4.0",
        "id": "105",
        "@timestamp": "2026-10-17T15:30:00.000Z",
        "sensorId": "camera-west",
        "objects": [
            {
                "object": {
                    "id": "42",
                    "type": "person",
                    "confidence": 0.96,
                    "bbox": {
                        "topleftx": 100,
                        "toplefty": 200,
                        "bottomrightx": 300,
                        "bottomrighty": 700,
                    },
                }
            },
            {
                "object": {
                    "id": "-1",
                    "type": "helmet",
                    "confidence": 0.91,
                    "bbox": {"left": 150, "top": 210, "width": 80, "height": 60},
                }
            },
        ],
    }
    meta = adapter.parse_payload(ds_payload)
    assert meta.camera_id == "camera-west"
    assert meta.frame_id == 105
    assert len(meta.detections) == 2
    assert meta.detections[0].track_id == 42
    assert meta.detections[0].class_name == "person"
    assert meta.detections[0].box.to_list() == [100.0, 200.0, 300.0, 700.0]
    assert meta.detections[1].track_id is None
    assert meta.detections[1].box.to_list() == [150.0, 210.0, 230.0, 270.0]


def test_deepstream_pipe_delimited_json_schema():
    adapter = PipeGenAdapter(format_mode="auto", bbox_format="xywh")
    payload = {
        "sensorId": "cam-gate",
        "frameId": 50,
        "ts": 12345.67,
        "objects": [
            "10|0|100|200|50|120|0.95",
            "-1|1|110|205|30|25|0.88",
        ],
    }
    meta = adapter.parse_payload(payload)
    assert meta.camera_id == "cam-gate"
    assert meta.frame_id == 50
    assert len(meta.detections) == 2
    assert meta.detections[0].track_id == 10
    assert meta.detections[0].class_name == "person"
    assert meta.detections[0].box.to_list() == [100.0, 200.0, 150.0, 320.0]


def test_deepstream_pipe_delimited_raw_string():
    adapter = PipeGenAdapter()
    raw_str = "100|cam-01|123456.78|5|0|10|20|100|200|0.93#-1|1|15|22|30|30|0.89"
    meta = adapter.parse_payload(raw_str)
    assert meta.frame_id == 100
    assert meta.camera_id == "cam-01"
    assert len(meta.detections) == 2


def test_bbox_normalized_scaling():
    adapter = PipeGenAdapter(bbox_normalized=True)
    payload = {
        "frame_id": 1,
        "frame": {"width": 1000, "height": 500},
        "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [0.1, 0.2, 0.5, 0.8]}],
    }
    meta = adapter.parse_payload(payload)
    assert len(meta.detections) == 1
    # 0.1 * 1000 = 100, 0.2 * 500 = 100, 0.5 * 1000 = 500, 0.8 * 500 = 400
    assert meta.detections[0].box.to_list() == [100.0, 100.0, 500.0, 400.0]


def test_timestamp_formats_iso_and_pts():
    adapter_iso = PipeGenAdapter()
    meta_iso = adapter_iso.parse_payload(
        {
            "frame_id": 1,
            "timestamp": "2026-10-17T12:00:00Z",
            "objects": [],
        }
    )
    assert meta_iso.ts > 1700000000.0

    adapter_pts = PipeGenAdapter(timestamp_format="pts_fps", fps=25.0)
    meta_pts = adapter_pts.parse_payload(
        {
            "frame_id": 50,
            "objects": [],
        }
    )
    # 50 frames at 25 fps = 2.0s
    assert meta_pts.ts == 2.0


def test_fuzz_malformed_json_does_not_crash():
    adapter = PipeGenAdapter()
    # Malformed strings
    for bad in ["", "{bad json", "null", "12345", "[]", "None", "{'unquoted': 123}"]:
        meta = adapter.parse_payload(bad)
        assert isinstance(meta, FrameMeta)
    assert adapter.adapter_rejects_total > 0


def test_fuzz_nan_and_inf_coordinates_rejected():
    adapter = PipeGenAdapter()
    payload = {
        "frame_id": 1,
        "objects": [
            {"track_id": 1, "class": "person", "conf": 0.9, "bbox": [float("nan"), 10, 50, 100]},
            {"track_id": 2, "class": "person", "conf": 0.9, "bbox": [10, float("inf"), 50, 100]},
            {"track_id": 3, "class": "person", "conf": 0.9, "bbox": [10, 20, 50, 100]},  # valid
        ],
    }
    meta = adapter.parse_payload(payload)
    # The 2 invalid objects should be safely rejected while the valid one is kept
    assert len(meta.detections) == 1
    assert meta.detections[0].track_id == 3
    assert adapter.adapter_rejects_total >= 2


def test_fuzz_zero_and_negative_size_boxes_rejected():
    adapter = PipeGenAdapter()
    payload = {
        "frame_id": 1,
        "objects": [
            {
                "track_id": 1,
                "class": "person",
                "conf": 0.9,
                "bbox": [50, 50, 50, 50],
            },  # zero width/height
            {
                "track_id": 2,
                "class": "person",
                "conf": 0.9,
                "bbox": [100, 100, 50, 50],
            },  # inverted coords fixed by Box or rejected
            {"track_id": 3, "class": "person", "conf": 0.9, "bbox": [0, 0, 10, 0]},  # zero height
            {"track_id": 4, "class": "person", "conf": 0.9, "bbox": [10, 20, 30, 40]},  # valid
        ],
    }
    meta = adapter.parse_payload(payload)
    assert any(d.track_id == 4 for d in meta.detections)
    assert adapter.adapter_rejects_total > 0


def test_fuzz_missing_and_wrong_types():
    adapter = PipeGenAdapter()
    payload = {
        "frame_id": "not-an-int",
        "objects": "not-a-list",
    }
    meta = adapter.parse_payload(payload)
    assert meta.frame_id == 0
    assert len(meta.detections) == 0


def test_huge_payload_handling():
    adapter = PipeGenAdapter()
    objs = [
        {"track_id": i, "class": "person", "conf": 0.9, "bbox": [10, 20, 30, 40]}
        for i in range(2000)
    ]
    meta = adapter.parse_payload({"frame_id": 1, "objects": objs})
    assert len(meta.detections) == 2000


def test_diagnose_payload_reports_best_format_and_fields():
    adapter = PipeGenAdapter()
    sample = {
        "sensorId": "gate-1",
        "id": 100,
        "objects": [
            {
                "object": {
                    "id": "1",
                    "type": "person",
                    "confidence": 0.95,
                    "bbox": {"left": 10, "top": 20, "width": 30, "height": 40},
                }
            }
        ],
    }
    diag = adapter.diagnose_payload(json.dumps(sample))
    assert diag["parsed_successfully"] is True
    assert diag["detected_format"] == "deepstream_array"
    assert diag["detections_count"] == 1
    assert "person" in diag["classes_detected"]


def test_json_file_metadata_tailer(tmp_path: Path):
    jsonl_file = tmp_path / "stream.jsonl"
    adapter = PipeGenAdapter()
    tailer = JsonFileMetadataTailer(jsonl_file, adapter)

    # Write header and 2 lines
    content = (
        '{"_sentinel_capture_header": true, "version": "0.1.0"}\n'
        '{"frame_id": 1, "ts": 1.0, "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [1,2,3,4]}]}\n'
        '{"frame_id": 2, "ts": 2.0, "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [1,2,3,4]}]}\n'
    )
    jsonl_file.write_text(content, encoding="utf-8")

    frames = list(tailer.iter_frames(stop_at_eof=True))
    assert len(frames) == 2
    assert frames[0].frame_id == 1
    assert frames[1].frame_id == 2


def test_capture_and_replay_roundtrip_deterministic(tmp_path: Path):
    from sentinel.config import load_rules_config
    from sentinel.domain.rules import RuleEngine
    from sentinel.domain.zones import ZoneManager

    capture_file = tmp_path / "capture_test.ndjson"
    header = {"_sentinel_capture_header": True, "source": "test"}
    frame1 = {
        "camera_id": "cam-01",
        "frame_id": 1,
        "ts": 1.0,
        "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [200, 700, 300, 900]}],
    }
    frame2 = {
        "camera_id": "cam-01",
        "frame_id": 2,
        "ts": 2.0,
        "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [200, 700, 300, 900]}],
    }
    frame3 = {
        "camera_id": "cam-01",
        "frame_id": 3,
        "ts": 3.5,
        "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [200, 700, 300, 900]}],
    }
    with open(capture_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        f.write(json.dumps(frame1) + "\n")
        f.write(json.dumps(frame2) + "\n")
        f.write(json.dumps(frame3) + "\n")

    adapter = PipeGenAdapter()
    rules_cfg = load_rules_config("config/rules.yaml")
    zones = ZoneManager.from_file("config/zones.json")
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=zones)

    incidents = []
    with open(capture_file, "r", encoding="utf-8") as f:
        for line in f:
            if "_sentinel_capture_header" in line or not line.strip():
                continue
            meta = adapter.parse_payload(line)
            raised = engine.process_frame(meta)
            incidents.extend(raised)

    # 4s without helmet in walkway should trigger NO_HELMET
    assert any(inc.type == "NO_HELMET" for inc in incidents)
