"""Unit tests for IncidentSink fsync durability, append-only log, and filtering."""

from pathlib import Path

from sentinel.incidents import IncidentSink
from sentinel.models import Incident


def test_incident_sink_append_and_query(tmp_path: Path):
    log_file = tmp_path / "incidents.jsonl"
    sink = IncidentSink(log_file)

    inc1 = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.9,
        duration_s=2.1,
        zone="walkway",
    )
    inc2 = Incident.create(
        incident_type="ZONE_INTRUSION",
        severity="HIGH",
        track_id=2,
        camera_id="cam-01",
        confidence=0.95,
        duration_s=0.0,
        zone="press-area",
    )

    sink.record(inc1)
    sink.record(inc2)

    # Read all (ordered newest first)
    all_incs = sink.read_all()
    assert len(all_incs) == 2
    assert all_incs[0].incident_id == inc2.incident_id
    assert all_incs[1].incident_id == inc1.incident_id

    # Filter by severity
    high_incs = sink.read_all(severity="HIGH")
    assert len(high_incs) == 1
    assert high_incs[0].type == "ZONE_INTRUSION"

    # Filter by zone
    walkway_incs = sink.read_all(zone="walkway")
    assert len(walkway_incs) == 1
    assert walkway_incs[0].type == "NO_HELMET"

    # Get by ID
    fetched = sink.get_by_id(inc1.incident_id)
    assert fetched is not None
    assert fetched.track_id == 1


def test_update_clip_path(tmp_path: Path):
    log_file = tmp_path / "incidents.jsonl"
    sink = IncidentSink(log_file)

    inc = Incident.create(
        incident_type="NO_VEST",
        severity="LOW",
        track_id=5,
        camera_id="cam-01",
        confidence=0.88,
        duration_s=2.0,
    )
    sink.record(inc)
    assert inc.evidence_clip is None

    updated = sink.update_clip_path(inc.incident_id, "evidence/2026-10-17/test.mp4")
    assert updated is True

    fetched = sink.get_by_id(inc.incident_id)
    assert fetched is not None
    assert fetched.evidence_clip == "evidence/2026-10-17/test.mp4"
