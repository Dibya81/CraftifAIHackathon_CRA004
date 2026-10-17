"""FastAPI REST and WebSocket service for SiteSentinel.

Endpoints:
- GET /api/health
- GET /api/incidents?limit&since&type&zone&severity
- GET /api/incidents/{id}
- POST /api/incidents/{id}/ack
- POST /api/incidents/{id}/note
- GET/PUT /api/zones
- GET /api/zones/snapshot
- GET /api/stats?window=
- GET /api/system
- GET /api/system/engine-report
- WS /ws/live
- Static mount for /evidence
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sentinel.config import (
    SentinelConfig,
    ZonesConfig,
    load_sentinel_config,
)
from sentinel.incidents import IncidentSink
from sentinel.zones import ZoneManager

logger = logging.getLogger("sentinel.api")

START_TIME = time.time()


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class AckRequest(BaseModel):
    user: Optional[str] = "operator"
    comment: Optional[str] = None


class NoteRequest(BaseModel):
    note: str = Field(..., min_length=1)
    author: Optional[str] = "operator"


class HealthResponse(BaseModel):
    status: str
    uptime_s: float
    camera: str
    mqtt: str
    engine_precision: str
    fps: float
    latency_ms: float
    gpu_util: Optional[float]
    gpu_power_w: Optional[float]
    ts: float


class StatsResponse(BaseModel):
    window: str
    total_incidents: int
    by_type: Dict[str, int]
    by_zone: Dict[str, int]
    by_severity: Dict[str, int]
    by_hour: List[Dict[str, Any]]
    compliance_percentage: float


class SystemResponse(BaseModel):
    camera_id: str
    camera: str
    mqtt: str
    engine_precision: str
    fps: float
    latency_ms: float
    gpu_util: Optional[float]
    gpu_power_w: Optional[float]
    gpu_temp_c: Optional[float]
    uptime_s: float
    timestamp: str


# ---------------------------------------------------------------------------
# Global State & WebSocket Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for live incident and telemetry streaming."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.discard(connection)


class AppState:
    """Container for API runtime state, loaded singletons, and cached snapshots."""

    def __init__(self) -> None:
        self.config: SentinelConfig = SentinelConfig()
        self.incident_sink: IncidentSink = IncidentSink()
        self.zone_manager: ZoneManager = ZoneManager.from_file()
        self.ws_manager: ConnectionManager = ConnectionManager()
        self.latest_snapshot: Optional[np.ndarray] = None
        self.acknowledged_incidents: Dict[str, Dict[str, Any]] = {}
        self.incident_notes: Dict[str, List[Dict[str, Any]]] = {}

        # Default telemetry metrics
        self.fps: float = 25.0
        self.latency_ms: float = 16.5
        self.engine_precision: str = "INT8"
        self.mqtt_status: str = "up"
        self.camera_status: str = "up"


state = AppState()


def get_gpu_metrics() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Queries nvidia-smi if present for GPU utilization (%), power (W), and temp (C)."""
    if not shutil.which("nvidia-smi"):
        return None, None, None
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,power.draw,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.0)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            util = float(parts[0]) if len(parts) > 0 and parts[0] else None
            power = float(parts[1]) if len(parts) > 1 and parts[1] else None
            temp = float(parts[2]) if len(parts) > 2 and parts[2] else None
            return util, power, temp
    except Exception:
        pass
    return None, None, None


# ---------------------------------------------------------------------------
# FastAPI App Lifecycle & Configuration
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load configurations
    try:
        state.config = load_sentinel_config("config/sentinel.yaml")
        state.incident_sink = IncidentSink(state.config.paths.incidents_log)
        state.zone_manager = ZoneManager.from_file(state.config.paths.zones)
    except Exception as e:
        logger.warning("Could not fully load initial config: %s (using defaults)", e)

    # Ensure evidence dir exists
    Path("evidence").mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown


app = FastAPI(title="SiteSentinel API", lifespan=lifespan)

# Enable CORS for dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mount for evidence clips and thumbnails
evidence_path = Path("evidence")
evidence_path.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(evidence_path)), name="evidence")


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    gpu_util, gpu_power, _ = get_gpu_metrics()
    return HealthResponse(
        status="ok" if state.camera_status == "up" and state.mqtt_status == "up" else "degraded",
        uptime_s=round(time.time() - START_TIME, 1),
        camera=state.camera_status,
        mqtt=state.mqtt_status,
        engine_precision=state.engine_precision,
        fps=state.fps,
        latency_ms=state.latency_ms,
        gpu_util=gpu_util,
        gpu_power_w=gpu_power,
        ts=time.time(),
    )


@app.get("/api/incidents")
def list_incidents(
    limit: Optional[int] = Query(default=50, ge=1, le=1000),
    since: Optional[str] = None,
    type: Optional[str] = None,
    zone: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Dict[str, Any]]:
    incidents = state.incident_sink.read_all(
        limit=limit,
        since_iso=since,
        incident_type=type,
        zone=zone,
        severity=severity,
    )
    results = []
    for inc in incidents:
        d = inc.to_dict()
        d["acknowledged"] = inc.incident_id in state.acknowledged_incidents
        d["ack_meta"] = state.acknowledged_incidents.get(inc.incident_id)
        d["notes"] = state.incident_notes.get(inc.incident_id, [])
        results.append(d)
    return results


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> Dict[str, Any]:
    inc = state.incident_sink.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    d = inc.to_dict()
    d["acknowledged"] = inc.incident_id in state.acknowledged_incidents
    d["ack_meta"] = state.acknowledged_incidents.get(inc.incident_id)
    d["notes"] = state.incident_notes.get(inc.incident_id, [])
    return d


@app.post("/api/incidents/{incident_id}/ack")
async def acknowledge_incident(incident_id: str, req: Optional[AckRequest] = None) -> Dict[str, Any]:
    inc = state.incident_sink.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    meta = {
        "acked_at": datetime.now(timezone.utc).isoformat(),
        "user": req.user if req else "operator",
        "comment": req.comment if req else None,
    }
    state.acknowledged_incidents[incident_id] = meta

    # Broadcast event
    msg = {
        "event": "incident_acked",
        "incident_id": incident_id,
        "ack_meta": meta,
        "ts": time.time(),
    }
    await state.ws_manager.broadcast(msg)
    return {"status": "acknowledged", "incident_id": incident_id, "meta": meta}


@app.post("/api/incidents/{incident_id}/note")
def add_incident_note(incident_id: str, req: NoteRequest) -> Dict[str, Any]:
    inc = state.incident_sink.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    note_entry = {
        "note": req.note,
        "author": req.author,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state.incident_notes.setdefault(incident_id, []).append(note_entry)
    return {"status": "noted", "incident_id": incident_id, "note": note_entry}


@app.get("/api/zones")
def get_zones() -> Dict[str, Any]:
    zones_file = Path("config/zones.json")
    if zones_file.exists():
        return json.loads(zones_file.read_text(encoding="utf-8"))
    return {"frame": {"width": 1920, "height": 1080}, "zones": []}


@app.put("/api/zones")
async def update_zones(zones_config: ZonesConfig) -> Dict[str, Any]:
    """Validates polygons, writes config/zones.json atomically, and hot-reloads the ZoneManager."""
    zones_file = Path("config/zones.json")
    zones_file.parent.mkdir(parents=True, exist_ok=True)

    data = zones_config.model_dump()
    json_str = json.dumps(data, indent=2)

    # Atomic write via temporary file
    tmp_path = zones_file.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(zones_file)

    # Hot-reload in memory
    state.zone_manager = ZoneManager(zones_config)
    logger.info("Hot-reloaded zones (%d zones configured)", len(zones_config.zones))

    # Broadcast zone update over WebSocket
    await state.ws_manager.broadcast({
        "event": "zones_updated",
        "zones_count": len(zones_config.zones),
        "ts": time.time(),
    })
    return {"status": "zones_updated", "zones_count": len(zones_config.zones)}


@app.get("/api/zones/snapshot")
def get_zone_snapshot() -> Response:
    """Returns the latest still frame as a JPEG image for the zone editor."""
    img = state.latest_snapshot
    if img is None:
        # Generate an annotated blank canvas if no frame has arrived yet
        img = np.full((1080, 1920, 3), (30, 42, 51), dtype=np.uint8)
        cv2.putText(img, "SiteSentinel Video Feed", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (244, 245, 246), 2)
        cv2.putText(img, "Ready for zone polygon authoring", (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)

    success, encoded = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode frame snapshot.")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/api/stats", response_model=StatsResponse)
def get_stats(window: str = "24h") -> StatsResponse:
    incidents = state.incident_sink.read_all()

    by_type: Dict[str, int] = {}
    by_zone: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    hourly_buckets: Dict[str, int] = {}

    for inc in incidents:
        by_type[inc.type] = by_type.get(inc.type, 0) + 1
        zone_label = inc.zone or "unassigned"
        by_zone[zone_label] = by_zone.get(zone_label, 0) + 1
        by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1

        # Hourly bucket (YYYY-MM-DD HH:00)
        try:
            hour_str = inc.timestamp[:13] + ":00"
            hourly_buckets[hour_str] = hourly_buckets.get(hour_str, 0) + 1
        except Exception:
            pass

    by_hour = [{"hour": k, "count": v} for k, v in sorted(hourly_buckets.items())]

    # Calculate compliance percentage
    total = len(incidents)
    compliance = max(0.0, min(100.0, 100.0 - (total * 2.5))) if total > 0 else 100.0

    return StatsResponse(
        window=window,
        total_incidents=total,
        by_type=by_type,
        by_zone=by_zone,
        by_severity=by_severity,
        by_hour=by_hour,
        compliance_percentage=round(compliance, 1),
    )


@app.get("/api/system", response_model=SystemResponse)
def get_system() -> SystemResponse:
    gpu_util, gpu_power, gpu_temp = get_gpu_metrics()
    return SystemResponse(
        camera_id=state.config.camera_id,
        camera=state.camera_status,
        mqtt=state.mqtt_status,
        engine_precision=state.engine_precision,
        fps=state.fps,
        latency_ms=state.latency_ms,
        gpu_util=gpu_util,
        gpu_power_w=gpu_power,
        gpu_temp_c=gpu_temp,
        uptime_s=round(time.time() - START_TIME, 1),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/system/engine-report")
def get_engine_report() -> Dict[str, Any]:
    """Serves the parsed PipeGen FP16 vs INT8 comparison report from reports/engine_comparison.json."""
    report_file = Path("reports/engine_comparison.json")
    if not report_file.exists():
        return {
            "status": "pending_data",
            "message": "PipeGen engine speed report not yet ingested. Run tools/engine_report.py to generate.",
            "data": None,
        }
    try:
        return json.loads(report_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read engine report: {e}")


# ---------------------------------------------------------------------------
# WebSocket Live Feed
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket) -> None:
    """Streams live incident events, ack updates, and telemetry heartbeats."""
    await state.ws_manager.connect(websocket)
    try:
        # Send initial snapshot upon connection
        gpu_util, gpu_power, _ = get_gpu_metrics()
        initial_msg = {
            "event": "initial_state",
            "uptime_s": round(time.time() - START_TIME, 1),
            "camera": state.camera_status,
            "mqtt": state.mqtt_status,
            "engine_precision": state.engine_precision,
            "fps": state.fps,
            "latency_ms": state.latency_ms,
            "gpu_util": gpu_util,
            "gpu_power_w": gpu_power,
            "recent_incidents": [inc.to_dict() for inc in state.incident_sink.read_all(limit=10)],
            "ts": time.time(),
        }
        await websocket.send_json(initial_msg)

        while True:
            # Keep connection alive; accept any ping or client message
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        state.ws_manager.disconnect(websocket)
    except Exception:
        state.ws_manager.disconnect(websocket)
