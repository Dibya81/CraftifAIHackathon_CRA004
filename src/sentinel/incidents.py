"""Incident model, JSONL append-only log and MQTT publishing."""
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Incident:
    incident_id: str
    timestamp: str
    camera_id: str
    type: str          # NO_HELMET | NO_VEST | ZONE_INTRUSION | DANGER_DWELL
    severity: str      # LOW | MEDIUM | HIGH
    track_id: int
    zone: Optional[str]
    confidence: float
    duration_s: float
    evidence_clip: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
