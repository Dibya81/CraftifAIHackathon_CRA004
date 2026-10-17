"""Unit and integration tests for EvidenceWriter, RingBuffer, and privacy enforcement."""

from pathlib import Path

import numpy as np
import pytest

from sentinel.config import EvidenceConfig, PathsConfig, PrivacyConfig, SentinelConfig
from sentinel.evidence import EvidenceWriter, PrivacyViolationError, RingBuffer
from sentinel.models import Incident
from tools.privacy_audit import run_privacy_audit


@pytest.mark.tc("TC-18")
def test_privacy_enforcement_refuses_unblurred_source(tmp_path: Path):
    """Hard rule: refuses to start or persist if source is not certified blurred."""
    cfg = SentinelConfig(
        paths=PathsConfig(evidence_dir=str(tmp_path / "evidence")),
        privacy=PrivacyConfig(require_blurred_source=True),
    )

    with pytest.raises(PrivacyViolationError) as exc_info:
        EvidenceWriter(config=cfg, is_source_blurred=False)
    assert "refusing to initialize" in str(exc_info.value).lower()


@pytest.mark.tc("TC-17")
def test_ring_buffer_rollover():
    rb = RingBuffer(max_frames=5)
    dummy_frame = np.zeros((10, 10, 3), dtype=np.uint8)

    for i in range(10):
        rb.append(float(i), dummy_frame)

    assert len(rb) == 5
    snapshot = rb.snapshot()
    # Oldest frames dropped off, remaining are 5.0 to 9.0
    timestamps = [ts for ts, _ in snapshot]
    assert timestamps == [5.0, 6.0, 7.0, 8.0, 9.0]


@pytest.mark.tc("TC-17")
def test_evidence_clip_and_thumbnail_creation(tmp_path: Path):
    evidence_dir = tmp_path / "evidence"
    cfg = SentinelConfig(
        paths=PathsConfig(evidence_dir=str(evidence_dir)),
        privacy=PrivacyConfig(require_blurred_source=True),
        evidence=EvidenceConfig(pre_seconds=1, post_seconds=1),
    )

    saved_clips = []

    def on_clip_saved(incident: Incident, clip_path: str):
        saved_clips.append((incident.incident_id, clip_path))

    writer = EvidenceWriter(
        config=cfg,
        is_source_blurred=True,
        on_clip_saved_callback=on_clip_saved,
    )

    dummy_frame = np.full((120, 160, 3), 40, dtype=np.uint8)

    # 1. Push 25 frames (1.0 second of pre-frames)
    for i in range(25):
        writer.push_frame(ts=i * 0.04, frame=dummy_frame)

    # 2. Trigger incident at t=1.0s
    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.9,
        duration_s=2.0,
    )
    writer.trigger_incident(inc, trigger_ts=1.0)

    # 3. Push 25 more frames (1.0 second of post-frames)
    for i in range(25, 51):
        writer.push_frame(ts=i * 0.04, frame=dummy_frame)

    writer.shutdown()

    # Verify clip and thumbnail were saved
    assert len(saved_clips) == 1
    inc_id, rel_path = saved_clips[0]
    assert inc_id == inc.incident_id

    mp4_files = list(evidence_dir.rglob("*.mp4"))
    jpg_files = list(evidence_dir.rglob("*.jpg"))
    assert len(mp4_files) == 1
    assert len(jpg_files) == 1
    assert mp4_files[0].stat().st_size > 0
    assert jpg_files[0].stat().st_size > 0

    # Run privacy audit on the clean/blurred output
    audit_passed = run_privacy_audit(str(evidence_dir))
    assert audit_passed is True
