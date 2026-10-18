"""Unit and integration tests for SQLite repository, outbox, and JSONL synchronization."""

from pathlib import Path

import pytest

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.adapters.storage.outbox_publisher import drain_outbox
from sentinel.adapters.storage.sqlite_repo import SQLiteIncidentRepository
from sentinel.domain.models import Incident, IncidentEvent, IncidentEventType
from sentinel.testing.fake_bus import FakeEventBus


@pytest.mark.tc("TC-16")
def test_sqlite_repo_migrations_and_foreign_keys(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    repo = SQLiteIncidentRepository(db_file)

    with repo._get_connection() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t["name"] for t in tables}

    expected_tables = {
        "schema_migrations",
        "incidents",
        "incident_notes",
        "evidence",
        "zones_versions",
        "outbox",
        "health_samples",
        "metrics_hourly",
    }
    assert expected_tables.issubset(table_names)


@pytest.mark.tc("TC-16")
def test_sqlite_repo_and_jsonl_synchronization(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    jsonl_file = tmp_path / "incidents.jsonl"
    jsonl_log = JSONLAuditLog(jsonl_file)
    repo = SQLiteIncidentRepository(db_path=db_file, jsonl_log=jsonl_log)

    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=10,
        camera_id="cam-01",
        confidence=0.92,
        duration_s=2.5,
        zone="walkway",
    )
    event = IncidentEvent.create(IncidentEventType.INCIDENT_CREATED.value, inc)

    repo.save_incident(inc, outbox_event=event)

    # Verify in DB
    db_inc = repo.get_incident(inc.incident_id)
    assert db_inc is not None
    assert db_inc.incident_id == inc.incident_id

    # Verify in JSONL
    jsonl_inc = jsonl_log.get_by_id(inc.incident_id)
    assert jsonl_inc is not None
    assert jsonl_inc.incident_id == inc.incident_id
    assert jsonl_inc.confidence == inc.confidence


@pytest.mark.tc("TC-19")
def test_keyset_pagination(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    repo = SQLiteIncidentRepository(db_file)

    # Seed 12 incidents with spaced timestamps
    for i in range(12):
        inc = Incident.create(
            incident_type="NO_HELMET",
            severity="MEDIUM",
            track_id=i,
            camera_id="cam-01",
            confidence=0.9,
            duration_s=2.0,
            timestamp=f"2026-10-17T12:{i:02d}:00.000000+00:00",
            incident_id=f"inc-{i:03d}",
        )
        repo.save_incident(inc)

    # Page 1: 5 items
    p1_items, c1 = repo.list_incidents(limit=5)
    assert len(p1_items) == 5
    assert c1 is not None
    assert p1_items[0].incident_id == "inc-011"

    # Page 2: next 5 items
    p2_items, c2 = repo.list_incidents(limit=5, cursor=c1)
    assert len(p2_items) == 5
    assert c2 is not None
    assert p2_items[0].incident_id == "inc-006"

    # Page 3: remaining 2 items
    p3_items, c3 = repo.list_incidents(limit=5, cursor=c2)
    assert len(p3_items) == 2
    assert c3 is None
    assert p3_items[-1].incident_id == "inc-000"


@pytest.mark.tc("TC-27")
def test_outbox_publisher_and_fault_resilience(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    repo = SQLiteIncidentRepository(db_file)
    bus = FakeEventBus()

    inc = Incident.create(
        incident_type="ZONE_INTRUSION",
        severity="HIGH",
        track_id=14,
        camera_id="cam-01",
        confidence=0.98,
        duration_s=1.2,
        zone="crane-drop",
    )
    event = IncidentEvent.create(IncidentEventType.INCIDENT_CREATED.value, inc)
    repo.save_incident(inc, outbox_event=event)

    # 1. Fault injection: simulate broker failure
    bus.failure_mode = True
    drained_failed = drain_outbox(repo, bus)
    assert drained_failed == 0
    # Pending outbox event still exists
    assert len(repo.get_pending_outbox_events()) == 1

    # 2. Restore broker connectivity
    bus.failure_mode = False
    drained_success = drain_outbox(repo, bus)
    assert drained_success == 1
    assert len(repo.get_pending_outbox_events()) == 0

    # 3. Assert message reached EventBus
    assert len(bus.published_messages) == 1
    topic, payload, qos, retain = bus.published_messages[0]
    assert topic == "sentinel/incidents"
    assert qos == 1
    assert payload["incident_id"] == inc.incident_id


@pytest.mark.tc("TC-19")
def test_ack_and_audit_notes(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    repo = SQLiteIncidentRepository(db_file)

    inc = Incident.create(
        incident_type="NO_VEST",
        severity="LOW",
        track_id=7,
        camera_id="cam-01",
        confidence=0.85,
        duration_s=3.0,
    )
    repo.save_incident(inc)

    # Ack with note
    acked = repo.ack_incident(
        inc.incident_id, acked_by="officer-sarah", note="Worker instructed to wear vest"
    )
    assert acked is not None
    assert acked.status == "acknowledged"
    assert acked.acked_by == "officer-sarah"
    assert len(acked.notes) == 1
    assert acked.notes[0]["author"] == "officer-sarah"

    # Add second note
    updated = repo.add_note(
        inc.incident_id,
        note_text="Worker retrieved vest from supply locker",
        author="supervisor-bob",
    )
    assert updated is not None
    assert len(updated.notes) == 2
    assert updated.notes[1]["author"] == "supervisor-bob"


def test_hash_chain_tamper_attacks(tmp_path: Path):
    """Test cryptographic resilience against edit, delete, reorder, and truncate attacks."""
    import json

    log_file = tmp_path / "chain_test.jsonl"
    audit_log = JSONLAuditLog(log_file)

    incidents = [
        Incident.create(
            incident_type="NO_HELMET",
            severity="MEDIUM",
            track_id=i,
            camera_id="cam-01",
            confidence=0.9,
            duration_s=2.0,
        )
        for i in range(1, 5)
    ]
    for inc in incidents:
        audit_log.record(inc)

    # 1. Clean verification
    valid, err = audit_log.verify_chain()
    assert valid is True
    assert err is None

    original_lines = log_file.read_text(encoding="utf-8").splitlines()

    # 2. Edit Attack: modify confidence in line 2
    tampered_lines = list(original_lines)
    item = json.loads(tampered_lines[1])
    item["confidence"] = 0.50
    tampered_lines[1] = json.dumps(item)
    log_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")
    valid, err = audit_log.verify_chain()
    assert valid is False
    assert "content modified" in err or "chain broken" in err

    # 3. Delete Attack: remove line 2
    tampered_lines = [original_lines[0], original_lines[2], original_lines[3]]
    log_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")
    valid, err = audit_log.verify_chain()
    assert valid is False
    assert "chain broken" in err

    # 4. Reorder Attack: swap line 1 and line 2
    tampered_lines = [original_lines[1], original_lines[0], original_lines[2], original_lines[3]]
    log_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")
    valid, err = audit_log.verify_chain()
    assert valid is False
    assert "chain broken" in err or "content modified" in err

    # 5. Truncate Attack: corrupt the last line
    tampered_lines = list(original_lines)
    tampered_lines[-1] = tampered_lines[-1][:25]
    log_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")
    valid, err = audit_log.verify_chain()
    assert valid is False
    assert "JSON parse error" in err or "chain broken" in err


def test_committed_sample_chain_integrity():
    """Verify that committed samples/incidents_sample.jsonl is intact and verified."""
    sample_file = Path("samples/incidents_sample.jsonl")
    assert sample_file.exists(), "samples/incidents_sample.jsonl must exist in repository."
    audit_log = JSONLAuditLog(sample_file)
    valid, err = audit_log.verify_chain()
    assert valid is True, f"Committed sample chain is broken: {err}"
