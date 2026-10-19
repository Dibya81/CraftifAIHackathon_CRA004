"""Mutation sanity checks: deliberate rule alterations must cause tests to fail."""

from __future__ import annotations

import copy

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.config import RulesConfig
from sentinel.domain.models import Box, Detection, FrameMeta, Incident
from sentinel.domain.rules import RuleEngine
from sentinel.domain.zones import Zone, ZoneManager


def make_test_setup():
    zones = [
        Zone(
            id="danger-zone",
            type="danger",
            required_ppe={"helmet", "vest"},
            raw_coords=[[100.0, 100.0], [500.0, 100.0], [500.0, 500.0], [100.0, 500.0]],
        )
    ]
    zm = ZoneManager(zones, ref_width=1000, ref_height=1000)
    rules_cfg = RulesConfig()
    rules_cfg.no_helmet.enabled = True
    rules_cfg.no_helmet.min_duration_s = 1.0
    return zm, rules_cfg


def test_mutation_zero_debounce_causes_premature_incident():
    """Mutation: If min_duration_s is mutated to 0.0, incident triggers on frame 0."""
    zm, rules_cfg = make_test_setup()
    normal_engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=zm)

    # Frame at t=0.0s (first observation)
    frame = FrameMeta(
        ts=0.0,
        frame_id=0,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.95, box=Box(200, 200, 300, 400), track_id=42)
        ],
    )

    # Normal engine: 0 incidents on frame 0
    normal_incs = normal_engine.process_frame(frame)
    assert len([i for i in normal_incs if i.type == "NO_HELMET"]) == 0

    # Mutated engine: debounce threshold mutated to 0
    mutated_cfg = copy.deepcopy(rules_cfg)
    mutated_cfg.no_helmet.min_duration_s = 0.0
    mutated_engine = RuleEngine(rules_cfg=mutated_cfg, zone_manager=zm)

    mutated_incs = mutated_engine.process_frame(frame)
    # The mutation MUST trigger the incident prematurely on frame 0
    assert len([i for i in mutated_incs if i.type == "NO_HELMET"]) == 1, (
        "Mutation sanity failed: zero debounce should have triggered incident immediately"
    )


def test_mutation_zone_displacement_fails_containment():
    """Mutation: If person box is moved outside the zone, zone intrusion must not trigger."""
    zm, rules_cfg = make_test_setup()
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=zm)

    # Person inside zone (200, 200)
    inside_frame = FrameMeta(
        ts=0.0,
        frame_id=1,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(200, 200, 250, 350), track_id=10)
        ],
    )
    inside_incs = engine.process_frame(inside_frame)
    # Danger zone entry triggers ZONE_INTRUSION immediately
    assert any(i.type == "ZONE_INTRUSION" for i in inside_incs)

    # Mutated coordinates: move person far outside zone (800, 800)
    outside_engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=zm)
    outside_frame = FrameMeta(
        ts=0.0,
        frame_id=2,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(800, 800, 900, 950), track_id=11)
        ],
    )
    outside_incs = outside_engine.process_frame(outside_frame)
    assert not any(i.type == "ZONE_INTRUSION" for i in outside_incs), (
        "Mutation sanity failed: person outside zone should never trigger ZONE_INTRUSION"
    )


def test_mutation_corrupted_hash_chain_fails_verification(tmp_path):
    """Mutation: Mutating an audit log entry hash causes verify_chain to return False."""
    log_file = tmp_path / "mutated_incidents.jsonl"
    audit = JSONLAuditLog(log_file)

    inc1 = Incident.create(
        incident_type="NO_HELMET",
        severity="LOW",
        track_id=1,
        camera_id="c1",
        confidence=0.9,
        duration_s=1.0,
    )
    inc2 = Incident.create(
        incident_type="NO_VEST",
        severity="MED",
        track_id=2,
        camera_id="c1",
        confidence=0.85,
        duration_s=1.0,
    )
    audit.record(inc1)
    audit.record(inc2)

    # Intact log passes
    valid, _ = audit.verify_chain()
    assert valid is True

    # Mutate previous_hash of second line
    lines = log_file.read_text(encoding="utf-8").splitlines()
    import json

    data = json.loads(lines[1])
    data["previous_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
    lines[1] = json.dumps(data)
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Mutation MUST cause verify_chain to fail
    mutated_audit = JSONLAuditLog(log_file)
    valid_mutated, err = mutated_audit.verify_chain()
    assert valid_mutated is False, (
        "Mutation sanity failed: corrupted previous_hash must fail validation"
    )
    assert "modified" in err.lower() or "mismatch" in err.lower()
