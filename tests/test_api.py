from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sentinel.api import app, state
from sentinel.incidents import IncidentSink
from sentinel.models import Incident


def setup_test_app(tmp_path: Path):
    log_file = tmp_path / "incidents.jsonl"
    state.incident_sink = IncidentSink(log_file)
    # Add a sample incident
    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.91,
        duration_s=2.3,
        zone="walkway",
    )
    state.incident_sink.record(inc)
    return inc


@pytest.mark.tc("TC-19")
def test_api_health(tmp_path: Path):
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "degraded"}
    assert "uptime_s" in data
    assert data["engine_precision"] == "INT8"
    assert data["fps"] == 25.0


def test_api_incidents_crud(tmp_path: Path):
    inc = setup_test_app(tmp_path)
    client = TestClient(app)

    # 1. List incidents
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["incident_id"] == inc.incident_id
    assert data[0]["acknowledged"] is False

    # 2. Get single incident
    resp_single = client.get(f"/api/incidents/{inc.incident_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["type"] == "NO_HELMET"

    # 3. Missing incident 404
    resp_404 = client.get("/api/incidents/nonexistent-uuid")
    assert resp_404.status_code == 404

    # 4. Acknowledge incident
    resp_ack = client.post(
        f"/api/incidents/{inc.incident_id}/ack", json={"user": "officer-dave", "comment": "Checked"}
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["status"] == "acknowledged"

    # Check that incident now lists as acknowledged
    resp_after = client.get(f"/api/incidents/{inc.incident_id}")
    assert resp_after.json()["acknowledged"] is True
    assert resp_after.json()["ack_meta"]["user"] == "officer-dave"

    # 5. Add note
    resp_note = client.post(
        f"/api/incidents/{inc.incident_id}/note",
        json={"note": "Worker retrieved helmet from locker."},
    )
    assert resp_note.status_code == 200
    resp_with_note = client.get(f"/api/incidents/{inc.incident_id}")
    assert len(resp_with_note.json()["notes"]) == 1
    assert "Worker retrieved helmet" in resp_with_note.json()["notes"][0]["note"]


@pytest.mark.tc("TC-20")
def test_api_zones_crud_and_snapshot(tmp_path: Path):
    client = TestClient(app)
    zones_file = Path("config/zones.json")
    original_zones = zones_file.read_text(encoding="utf-8") if zones_file.exists() else None

    try:
        # 1. Get zones
        resp = client.get("/api/zones")
        assert resp.status_code == 200
        assert "zones" in resp.json()

        # 2. Update zones
        new_zones = {
            "frame": {"width": 1920, "height": 1080},
            "zones": [
                {
                    "id": "new-zone",
                    "type": "safe",
                    "required_ppe": ["helmet"],
                    "polygon": [[10, 10], [100, 10], [100, 100], [10, 100]],
                }
            ],
        }
        resp_put = client.put("/api/zones", json=new_zones)
        assert resp_put.status_code == 200
        assert resp_put.json()["status"] == "zones_updated"
        assert resp_put.json()["zones_count"] == 1

        # 3. Snapshot endpoint returns image/jpeg
        resp_snap = client.get("/api/zones/snapshot")
        assert resp_snap.status_code == 200
        assert resp_snap.headers["content-type"] == "image/jpeg"
        assert len(resp_snap.content) > 100
    finally:
        if original_zones is not None:
            zones_file.write_text(original_zones, encoding="utf-8")


def test_api_stats_and_system(tmp_path: Path):
    setup_test_app(tmp_path)
    client = TestClient(app)

    # Stats
    resp_stats = client.get("/api/stats?window=24h")
    assert resp_stats.status_code == 200
    s_data = resp_stats.json()
    assert s_data["total_incidents"] >= 1
    assert "NO_HELMET" in s_data["by_type"]
    assert 0.0 <= s_data["compliance_percentage"] <= 100.0

    # System
    resp_sys = client.get("/api/system")
    assert resp_sys.status_code == 200
    sys_data = resp_sys.json()
    assert sys_data["engine_precision"] == "INT8"
    assert sys_data["camera_id"] == "cam-01"

    # Engine report endpoint
    resp_rep = client.get("/api/system/engine-report")
    assert resp_rep.status_code == 200


def test_api_websocket_live():
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as websocket:
        initial = websocket.receive_json()
        assert initial["event"] == "initial_state"
        assert "recent_incidents" in initial

        # Send ping
        websocket.send_text("ping")
        reply = websocket.receive_text()
        assert reply == "pong"


def test_api_stream_and_bulk_operations(tmp_path: Path):
    inc = setup_test_app(tmp_path)
    client = TestClient(app)

    # Stream status
    resp_stream = client.get("/api/stream/status")
    assert resp_stream.status_code == 200
    assert "active" in resp_stream.json()

    # Bulk ack
    resp_bulk = client.post("/api/incidents/bulk-ack", json={"incident_ids": [inc.incident_id], "user": "supervisor"})
    assert resp_bulk.status_code == 200
    assert resp_bulk.json()["count"] == 1

    # Export CSV
    resp_csv = client.get("/api/incidents/export.csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert inc.incident_id in resp_csv.text

    # Privacy audit
    resp_priv = client.get("/api/system/privacy-audit")
    assert resp_priv.status_code == 200
    assert resp_priv.json()["status"] == "passed"
