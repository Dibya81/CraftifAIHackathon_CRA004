"""Test real PipeGen sample payload fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLE_FILE = Path("tests/fixtures/pipegen_real_sample/sample_detection.json")


@pytest.mark.skipif(
    not SAMPLE_FILE.exists(), reason="PENDING real PipeGen sample"
)
def test_real_pipegen_sample_parsing():
    """Verify parsing a real hardware PipeGen sample payload."""
    from sentinel.adapters.pipegen import PipeGenAdapter

    adapter = PipeGenAdapter()
    meta = adapter.parse_payload(SAMPLE_FILE.read_text(encoding="utf-8"))
    assert meta.frame_id > 0
    assert len(meta.detections) > 0
