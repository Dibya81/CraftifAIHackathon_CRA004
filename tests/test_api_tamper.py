"""API contract and hash-chain tamper detection tests (TC-19, TC-31)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.adapters.storage.sqlite_repo import SQLiteIncidentRepository
from sentinel.adapters.video.mjpeg_relay import MJPEGRelay
from sentinel.config import SentinelConfig
from sentinel.domain.models import Incident, IncidentEvent, IncidentEventType
from sentinel.domain.zones import ZoneManager
from sentinel.interfaces.api.app import create_app


@pytest.fixture
def tamper_test_env(tmp_path: Path):
    db_file = tmp_path / "sentinel.db"
    jsonl_file = tmp_path / "incidents.jsonl"
    repo = SQLiteIncidentRepository(db_path=db_file, jsonl_log=JSONLAuditLog(jsonl_file))

    zones_dict = {
        "frame": {"width": 1920, "height": 1080},
        "zones": [
            {
                "id": "restricted-zone",
                "type": "restricted",
                "required_ppe": ["helmet", "vest"],
                "polygon": [[100, 100], [500, 100], [500, 500], [100, 500]],
            }
        ],
    }
    zm = ZoneManager.from_config_dict(zones_dict)
    relay = MJPEGRelay()

    cfg = SentinelConfig()
    cfg.paths.incidents_log = str(jsonl_file)
    cfg.paths.evidence_dir = str(tmp_path / "evidence")
    cfg.paths.zones = str(tmp_path / "zones.json")
    Path(cfg.paths.evidence_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.paths.zones).write_text(json.dumps(zones_dict), encoding="utf-8")

    app = create_app(config=cfg, repository=repo, zone_manager=zm, mjpeg_relay=relay)
    client = TestClient(app)
    return {
        "app": app,
        "client": client,
        "repo": repo,
        "jsonl_file": jsonl_file,
        "db_file": db_file,
    }


def test_api_log_integrity_intact(tamper_test_env):
    """Verifies that an intact audit log reports valid chain via /api/v1/system/log-integrity."""
    repo = tamper_test_env["repo"]
    client = tamper_test_env["client"]

    # Record 3 incidents sequentially with valid cryptographic hash chain
    for i in range(1, 4):
        inc = Incident.create(
            incident_type="NO_HELMET",
            severity="MEDIUM",
            track_id=i,
            camera_id="cam-01",
            zone="restricted-zone",
            confidence=0.92,
            duration_s=2.5,
        )
        evt = IncidentEvent.create(
            event_type=IncidentEventType.INCIDENT_CREATED.value,
            incident=inc,
        )
        repo.save_incident(incident=inc, outbox_event=evt)

    resp = client.get("/api/v1/system/log-integrity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PASS"
    assert data["valid"] is True
    assert data["count"] == 3
    assert "Log chain intact" in data["badge"]


def test_api_log_integrity_detects_hash_tampering(tamper_test_env):
    """Verifies that modifying a JSONL log line causes API integrity endpoint to report FAIL."""
    repo = tamper_test_env["repo"]
    client = tamper_test_env["client"]
    jsonl_file = tamper_test_env["jsonl_file"]

    # Create 3 incidents
    for i in range(1, 4):
        inc = Incident.create(
            incident_type="NO_VEST",
            severity="HIGH",
            track_id=i,
            camera_id="cam-01",
            zone="restricted-zone",
            confidence=0.88,
            duration_s=3.0,
        )
        evt = IncidentEvent.create(
            event_type=IncidentEventType.INCIDENT_CREATED.value,
            incident=inc,
        )
        repo.save_incident(incident=inc, outbox_event=evt)

    # Tamper with the second entry in the JSONL file
    lines = jsonl_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    tampered_entry = json.loads(lines[1])
    tampered_entry["severity"] = "LOW"  # Malicious modification of severity
    lines[1] = json.dumps(tampered_entry)
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # API integrity check must detect the tamper
    resp = client.get("/api/v1/system/log-integrity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAIL"
    assert data["valid"] is False
    assert data["error"] is not None
    assert "Chain broken" in data["badge"]
