"""FastAPI REST and WebSocket Service Contract tests (TC-19)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.adapters.storage.sqlite_repo import SQLiteIncidentRepository
from sentinel.adapters.video.mjpeg_relay import MJPEGRelay
from sentinel.config import SentinelConfig
from sentinel.domain.models import Incident
from sentinel.domain.zones import ZoneManager
from sentinel.interfaces.api.app import create_app


@pytest.fixture
def test_app_ctx(tmp_path: Path):
    db_file = tmp_path / "test.db"
    jsonl_file = tmp_path / "incidents.jsonl"
    repo = SQLiteIncidentRepository(db_path=db_file, jsonl_log=JSONLAuditLog(jsonl_file))

    zones_dict = {
        "frame": {"width": 1920, "height": 1080},
        "zones": [
            {
                "id": "danger-01",
                "type": "danger",
                "required_ppe": ["helmet", "vest"],
                "polygon": [[100, 100], [400, 100], [400, 400], [100, 400]],
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
    return {"app": app, "repo": repo, "tmp_path": tmp_path, "cfg": cfg}


@pytest.mark.tc("TC-19")
def test_tc19_openapi_schema_drift(test_app_ctx):
    """TC-19: Assert runtime OpenAPI schema matches committed docs/openapi.json."""
    app = test_app_ctx["app"]
    current_schema = app.openapi()

    openapi_file = Path("docs/openapi.json")
    assert openapi_file.exists(), "docs/openapi.json snapshot must exist."
    committed_schema = json.loads(openapi_file.read_text(encoding="utf-8"))

    # Assert paths and schemas match exactly
    assert current_schema["paths"].keys() == committed_schema["paths"].keys(), (
        "OpenAPI path definitions have drifted from docs/openapi.json."
    )


@pytest.mark.tc("TC-19")
def test_tc19_readiness_and_health(test_app_ctx):
    """TC-19: Verify /ready and /health endpoints."""
    client = TestClient(test_app_ctx["app"])

    resp_ready = client.get("/api/ready")
    assert resp_ready.status_code == 200
    r_data = resp_ready.json()
    assert r_data["status"] == "ready"
    assert r_data["database"] == "connected"
    assert r_data["evidence_dir"] == "writable"

    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    h_data = resp_health.json()
    assert h_data["status"] in {"ok", "degraded"}
    assert h_data["fps"] > 0


@pytest.mark.tc("TC-19")
def test_tc19_keyset_pagination_and_filters(test_app_ctx):
    """TC-19: Verify keyset pagination with cursor and filters on /api/incidents."""
    repo = test_app_ctx["repo"]
    client = TestClient(test_app_ctx["app"])

    # Seed 10 incidents with monotonically decreasing timestamps
    for i in range(10):
        inc = Incident.create(
            incident_type="NO_HELMET" if i % 2 == 0 else "NO_VEST",
            severity="HIGH" if i < 3 else "MEDIUM",
            track_id=100 + i,
            camera_id="cam-01",
            confidence=0.92,
            duration_s=2.5,
            zone="danger-01",
            timestamp=f"2026-10-17T12:00:{10 - i:02d}.000Z",
            incident_id=f"inc-seed-{i:03d}",
        )
        repo.record_incident(inc)

    # 1. Fetch first page with limit=4
    resp_p1 = client.get("/api/incidents?limit=4")
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert len(data_p1["items"]) == 4
    assert data_p1["next_cursor"] is not None

    # 2. Fetch second page with next_cursor
    cursor = data_p1["next_cursor"]
    resp_p2 = client.get(f"/api/incidents?limit=4&cursor={cursor}")
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) == 4

    # Ensure no overlap between page 1 and page 2
    ids_p1 = {item["incident_id"] for item in data_p1["items"]}
    ids_p2 = {item["incident_id"] for item in data_p2["items"]}
    assert ids_p1.isdisjoint(ids_p2), "Pages must not contain overlapping incident IDs."

    # 3. Filter by type
    resp_filt = client.get("/api/incidents?type=NO_HELMET")
    assert resp_filt.status_code == 200
    for itm in resp_filt.json()["items"]:
        assert itm["type"] == "NO_HELMET"


@pytest.mark.tc("TC-19")
def test_tc19_bulk_ack_and_notes(test_app_ctx):
    """TC-19: Test bulk acknowledge and notes addition."""
    repo = test_app_ctx["repo"]
    client = TestClient(test_app_ctx["app"])

    inc1 = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.9,
        duration_s=2.0,
    )
    inc2 = Incident.create(
        incident_type="NO_VEST",
        severity="LOW",
        track_id=2,
        camera_id="cam-01",
        confidence=0.88,
        duration_s=1.8,
    )
    repo.record_incident(inc1)
    repo.record_incident(inc2)

    # Bulk ack
    resp_bulk = client.post(
        "/api/incidents/bulk-ack",
        json={
            "incident_ids": [inc1.incident_id, inc2.incident_id],
            "user": "safety-lead",
            "comment": "Verified",
        },
    )
    assert resp_bulk.status_code == 200
    assert resp_bulk.json()["acknowledged_count"] == 2

    # Add note
    resp_note = client.post(
        f"/api/incidents/{inc1.incident_id}/notes",
        json={"note": "Safety briefing delivered to worker.", "author": "supervisor"},
    )
    assert resp_note.status_code == 200
    notes = resp_note.json()["notes"]
    assert len(notes) == 2
    assert any("Safety briefing delivered to worker." in str(n) for n in notes)


@pytest.mark.tc("TC-19")
def test_tc19_csv_export_stream(test_app_ctx):
    """TC-19: Verify CSV streaming export."""
    repo = test_app_ctx["repo"]
    client = TestClient(test_app_ctx["app"])

    inc = Incident.create(
        incident_type="ZONE_INTRUSION",
        severity="HIGH",
        track_id=42,
        camera_id="cam-01",
        confidence=0.95,
        duration_s=3.0,
        zone="danger-01",
    )
    repo.record_incident(inc)

    resp = client.get("/api/incidents/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert (
        "incident_id,timestamp,camera_id,type,severity,track_id,zone,confidence,duration_s,status"
        in content
    )
    assert inc.incident_id in content


@pytest.mark.tc("TC-19")
def test_tc19_evidence_path_traversal_defense(test_app_ctx):
    """TC-19: Assert path traversal protection blocks illegal file requests."""
    client = TestClient(test_app_ctx["app"])

    # Legitimate evidence file
    ev_dir = Path(test_app_ctx["cfg"].paths.evidence_dir)
    test_clip = ev_dir / "valid_clip.mp4"
    test_clip.write_bytes(b"dummy video data")

    resp_valid = client.get("/evidence/valid_clip.mp4")
    assert resp_valid.status_code == 200

    # Path traversal attack
    resp_attack = client.get("/evidence/../../../../etc/passwd")
    assert resp_attack.status_code in {403, 404}


@pytest.mark.tc("TC-19")
def test_tc19_zones_validation_rejection(test_app_ctx):
    """TC-19: Ensure invalid zone geometries return 422 Unprocessable Entity."""
    client = TestClient(test_app_ctx["app"])

    invalid_zone_data = {
        "frame": {"width": 1920, "height": 1080},
        "zones": [
            {
                "id": "bad-zone",
                "type": "restricted",
                "required_ppe": ["helmet"],
                "polygon": [[10, 10], [50, 50]],  # Only 2 points - invalid polygon!
            }
        ],
    }

    resp = client.put("/api/zones", json=invalid_zone_data)
    assert resp.status_code == 422


@pytest.mark.tc("TC-19")
def test_tc19_single_incident_and_ack(test_app_ctx):
    """TC-19: Get single incident and acknowledge it."""
    repo = test_app_ctx["repo"]
    client = TestClient(test_app_ctx["app"])

    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.91,
        duration_s=2.3,
        zone="danger-01",
    )
    repo.record_incident(inc)

    # Get single
    resp = client.get(f"/api/incidents/{inc.incident_id}")
    assert resp.status_code == 200
    assert resp.json()["type"] == "NO_HELMET"

    # Ack
    resp_ack = client.post(
        f"/api/incidents/{inc.incident_id}/ack",
        json={"user": "officer-dave", "comment": "Checked and confirmed"},
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["status"] == "acknowledged"


@pytest.mark.tc("TC-20")
def test_tc20_zones_snapshot_and_live_ws(test_app_ctx):
    """TC-20: Test zone snapshot JPEG and live websocket connection."""
    client = TestClient(test_app_ctx["app"])

    # Snapshot endpoint
    resp_snap = client.get("/api/zones/snapshot")
    assert resp_snap.status_code == 200
    assert resp_snap.headers["content-type"] == "image/jpeg"
    assert len(resp_snap.content) > 100

    # WebSocket /ws/live
    with client.websocket_connect("/ws/live") as ws:
        init_data = ws.receive_json()
        assert init_data["event"] == "initial_state"
        assert "recent_incidents" in init_data

        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_system_log_integrity_endpoint(test_app_ctx):
    client = TestClient(test_app_ctx["app"])
    resp = client.get("/api/system/log-integrity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PASS"
    assert data["valid"] is True
    assert "log_path" in data
