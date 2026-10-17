from pathlib import Path

import pytest

from sentinel.adapters.pipegen import JsonFileMetadataTailer, PipeGenAdapter
from sentinel.models import FrameMeta


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


def test_json_file_metadata_tailer(tmp_path: Path):
    jsonl_file = tmp_path / "stream.jsonl"
    adapter = PipeGenAdapter()
    tailer = JsonFileMetadataTailer(jsonl_file, adapter)

    # Write 2 lines to the file
    line1 = '{"frame_id": 1, "ts": 1.0, "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [1,2,3,4]}]}\n'
    line2 = '{"frame_id": 2, "ts": 2.0, "objects": [{"track_id": 1, "class": "person", "conf": 0.9, "bbox": [1,2,3,4]}]}\n'
    jsonl_file.write_text(line1 + line2, encoding="utf-8")

    frames = list(tailer.iter_frames(stop_at_eof=True))
    assert len(frames) == 2
    assert frames[0].frame_id == 1
    assert frames[1].frame_id == 2
