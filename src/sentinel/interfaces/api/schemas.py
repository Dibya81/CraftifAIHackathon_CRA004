"""Pydantic v2 schemas for SiteSentinel REST API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class AckRequest(BaseModel):
    user: Optional[str] = "safety-officer"
    comment: Optional[str] = None


class BulkAckRequest(BaseModel):
    incident_ids: List[str] = Field(..., min_length=1)
    user: Optional[str] = "safety-officer"
    comment: Optional[str] = None


class NoteRequest(BaseModel):
    note: str = Field(..., min_length=1)
    author: Optional[str] = "safety-officer"


class HealthResponse(BaseModel):
    status: str
    uptime_s: float
    camera: str
    mqtt: str
    engine_precision: str
    fps: float
    latency_ms: float
    gpu_util: Optional[float] = None
    gpu_power_w: Optional[float] = None
    ts: float


class ReadyResponse(BaseModel):
    status: str
    database: str
    event_bus: str
    evidence_dir: str
    timestamp: str


class IncidentResponse(BaseModel):
    incident_id: str
    timestamp: str
    camera_id: str
    type: str
    severity: str
    track_id: int
    zone: Optional[str] = None
    confidence: float
    duration_s: float
    evidence_clip: Optional[str] = None
    schema_version: str = "1.0"
    status: str = "open"
    acked_at: Optional[str] = None
    acked_by: Optional[str] = None
    notes: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_status: str = "pending"
    acknowledged: bool = False
    ack_meta: Optional[Dict[str, Any]] = None

    @classmethod
    def from_incident(cls, inc: Any) -> IncidentResponse:
        data = inc.to_dict() if hasattr(inc, "to_dict") else dict(inc)
        is_acked = data.get("status") == "acknowledged" or data.get("acked_at") is not None
        ack_meta = None
        if is_acked:
            ack_meta = {
                "acked_at": data.get("acked_at"),
                "user": data.get("acked_by") or "operator",
            }
        return cls(
            incident_id=data["incident_id"],
            timestamp=data["timestamp"],
            camera_id=data["camera_id"],
            type=data["type"],
            severity=data["severity"],
            track_id=data["track_id"],
            zone=data.get("zone"),
            confidence=float(data["confidence"]),
            duration_s=float(data["duration_s"]),
            evidence_clip=data.get("evidence_clip"),
            schema_version=data.get("schema_version", "1.0"),
            status=data.get("status", "open"),
            acked_at=data.get("acked_at"),
            acked_by=data.get("acked_by"),
            notes=data.get("notes") or [],
            evidence_status=data.get("evidence_status", "pending"),
            acknowledged=is_acked,
            ack_meta=ack_meta,
        )


class IncidentsListResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    next_cursor: Optional[str] = None


class StatsResponse(BaseModel):
    window: str
    total_incidents: int
    by_type: Dict[str, int]
    by_zone: Dict[str, int]
    by_severity: Dict[str, int]
    by_hour: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_percentage: float


class SystemResponse(BaseModel):
    camera_id: str
    camera: str
    mqtt: str
    engine_precision: str
    fps: float
    latency_ms: float
    gpu_util: Optional[float] = None
    gpu_power_w: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    uptime_s: float
    timestamp: str


class ServicesResponse(BaseModel):
    engine: str
    evidence: str
    api: str
    mqtt: str
    database: str
