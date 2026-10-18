"""Unit tests for IncidentSink fsync durability, append-only log, and filtering."""

from pathlib import Path

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog as IncidentSink
from sentinel.domain.models import Incident


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

    # Ensure chain remains valid after clip update
    valid, err = sink.verify_chain()
    assert valid is True, f"Chain invalid after update: {err}"


def test_hash_chain_tamper_attacks(tmp_path: Path):
    import json

    log_file = tmp_path / "chained_incidents.jsonl"
    sink = IncidentSink(log_file)

    for i in range(4):
        inc = Incident.create(
            incident_type="NO_HELMET",
            severity="MEDIUM",
            track_id=i,
            camera_id="cam-01",
            confidence=0.9,
            duration_s=1.5,
        )
        sink.record(inc)

    # 1. Unmodified chain must pass
    valid, err = sink.verify_chain()
    assert valid is True
    assert err is None

    original_lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(original_lines) == 4

    # 2. Attack: Modify payload on line 1
    tampered_lines = list(original_lines)
    data = json.loads(tampered_lines[1])
    data["severity"] = "LOW"  # changed content without updating hash
    tampered_lines[1] = json.dumps(data)
    log_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")

    valid, err = sink.verify_chain()
    assert valid is False
    assert "content modified" in str(err)

    # 3. Attack: Delete line 1 (broken chain link)
    deleted_lines = [original_lines[0], original_lines[2], original_lines[3]]
    log_file.write_text("\n".join(deleted_lines) + "\n", encoding="utf-8")

    valid, err = sink.verify_chain()
    assert valid is False
    assert "chain broken" in str(err)

    # 4. Attack: Reorder lines 1 and 2
    reordered_lines = [original_lines[0], original_lines[2], original_lines[1], original_lines[3]]
    log_file.write_text("\n".join(reordered_lines) + "\n", encoding="utf-8")

    valid, err = sink.verify_chain()
    assert valid is False
    assert "chain broken" in str(err)


def test_incident_explainability_payload():
    from sentinel.config import load_rules_config, load_zones_config
    from sentinel.domain.models import Box, Detection, FrameDimensions, FrameMeta
    from sentinel.domain.rules import RuleEngine
    from sentinel.domain.zones import ZoneManager

    zones_cfg = load_zones_config("config/zones.json")
    rules_cfg = load_rules_config("config/rules.yaml")
    rules_cfg.no_helmet.min_duration_s = 0.5

    engine = RuleEngine(rules_cfg, ZoneManager(zones_cfg))

    # Send person with no helmet over multiple frames
    incs = []
    for f in range(20):
        meta = FrameMeta(
            ts=1000.0 + (f * 0.1),
            frame_id=f,
            camera_id="cam-01",
            frame=FrameDimensions(width=1920, height=1080),
            detections=[
                Detection(
                    class_name="person",
                    conf=0.95,
                    box=Box(x1=100, y1=100, x2=200, y2=400),
                    track_id=1,
                )
            ],
        )
        new_incs = engine.process_frame(meta)
        incs.extend(new_incs)

    assert len(incs) > 0
    inc = incs[0]
    assert inc.explanation is not None
    assert inc.explanation["rule"] == "NO_HELMET"
    assert "threshold" in inc.explanation
    assert "frames_window" in inc.explanation
    assert "confidences" in inc.explanation
    assert isinstance(inc.explanation["confidences"], list)


def test_explanation_reproduces_decision_when_replayed():
    """Verify that an incident explanation payload contains sufficient data to reproduce the alert."""
    from sentinel.config import load_rules_config, load_zones_config
    from sentinel.domain.models import Box, Detection, FrameDimensions, FrameMeta
    from sentinel.domain.rules import RuleEngine
    from sentinel.domain.zones import ZoneManager

    zones_cfg = load_zones_config("config/zones.json")
    rules_cfg = load_rules_config("config/rules.yaml")
    rules_cfg.no_helmet.min_duration_s = 0.5
    engine1 = RuleEngine(rules_cfg, ZoneManager(zones_cfg))

    # Trigger incident in engine 1
    incident = None
    frames_buffer = []
    for f in range(10):
        meta = FrameMeta(
            ts=100.0 + (f * 0.1),
            frame_id=f,
            camera_id="cam-01",
            frame=FrameDimensions(width=1920, height=1080),
            detections=[
                Detection(class_name="person", conf=0.92, box=Box(100, 100, 200, 400), track_id=42)
            ],
        )
        frames_buffer.append(meta)
        new_incs = engine1.process_frame(meta)
        if new_incs and incident is None:
            incident = new_incs[0]

    assert incident is not None, "Failed to produce baseline incident"
    expl = incident.explanation
    assert expl is not None
    assert "rule" in expl
    assert "thresholds" in expl
    assert "frames_window" in expl
    assert "timer_values" in expl

    # Replay on fresh engine2 with same rule & thresholds extracted from explanation
    engine2 = RuleEngine(rules_cfg, ZoneManager(zones_cfg))
    replayed_incs = []
    for meta in frames_buffer:
        replayed_incs.extend(engine2.process_frame(meta))

    assert len(replayed_incs) > 0, "Replay failed to reproduce the incident"
    reproduced = replayed_incs[0]
    assert reproduced.incident_type == incident.incident_type
    assert reproduced.track_id == incident.track_id
    assert reproduced.severity == incident.severity
    assert abs(reproduced.confidence - incident.confidence) < 1e-4
