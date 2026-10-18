"""Domain models for SiteSentinel.

Defines Box, Detection, FrameMeta, Track, Incident, and IncidentEvent with immutable
characteristics and strict typing matching architecture specifications §5.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class IncidentType(str, enum.Enum):
    NO_HELMET = "NO_HELMET"
    NO_VEST = "NO_VEST"
    ZONE_INTRUSION = "ZONE_INTRUSION"
    DANGER_DWELL = "DANGER_DWELL"


class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"


class EvidenceStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class IncidentEventType(str, enum.Enum):
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_ACKED = "incident_acked"
    INCIDENT_NOTE_ADDED = "incident_note_added"


@dataclass(frozen=True)
class Box:
    """Bounding box defined by [x1, y1, x2, y2] coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        min_x, max_x = min(self.x1, self.x2), max(self.x1, self.x2)
        min_y, max_y = min(self.y1, self.y2), max(self.y1, self.y2)
        object.__setattr__(self, "x1", min_x)
        object.__setattr__(self, "x2", max_x)
        object.__setattr__(self, "y1", min_y)
        object.__setattr__(self, "y2", max_y)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def foot_point(self) -> Tuple[float, float]:
        """Bottom-center of the bounding box."""
        return ((self.x1 + self.x2) / 2.0, self.y2)

    def sub_region(self, top_frac: float, bottom_frac: float) -> Box:
        """Extract a vertical sub-box from a fraction of height from top."""
        h = self.height
        return Box(
            x1=self.x1,
            y1=self.y1 + top_frac * h,
            x2=self.x2,
            y2=self.y1 + bottom_frac * h,
        )

    def intersection_area(self, other: Box) -> float:
        """Area of overlap between two bounding boxes."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        return iw * ih

    def intersection_over_other(self, other: Box) -> float:
        """Intersection area divided by other box's area (IoA)."""
        other_area = other.area
        if other_area <= 0.0:
            return 0.0
        return self.intersection_area(other) / other_area

    def rescale(self, scale_x: float, scale_y: float) -> Box:
        return Box(
            x1=self.x1 * scale_x,
            y1=self.y1 * scale_y,
            x2=self.x2 * scale_x,
            y2=self.y2 * scale_y,
        )

    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass(frozen=True)
class Detection:
    """A detected object with class name, confidence, bounding box, and optional track ID."""

    class_name: str
    conf: float
    box: Box
    track_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class": self.class_name,
            "conf": self.conf,
            "bbox": self.box.to_list(),
            "track_id": self.track_id,
        }


@dataclass(frozen=True)
class FrameDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class FrameMeta:
    """Per-frame detection payload with timestamp, frame ID, and detections."""

    ts: float  # epoch seconds (float)
    frame_id: int
    camera_id: str
    detections: List[Detection] = field(default_factory=list)
    frame: Optional[FrameDimensions] = None


@dataclass(frozen=True)
class Track:
    """Represents an active or historical person track."""

    track_id: int
    first_seen_ts: float
    last_seen_ts: float
    last_box: Box
    current_zone: Optional[str] = None
    has_helmet: bool = False
    has_vest: bool = False


@dataclass
class Incident:
    """A safety incident raised by the rule engine (architecture specification §5)."""

    incident_id: str
    timestamp: str  # ISO-8601 UTC
    camera_id: str
    type: str  # NO_HELMET | NO_VEST | ZONE_INTRUSION | DANGER_DWELL
    severity: str  # LOW | MEDIUM | HIGH
    track_id: int
    zone: Optional[str]
    confidence: float
    duration_s: float
    evidence_clip: Optional[str] = None
    # Hexagonal extensions
    schema_version: str = "1.0"
    status: str = "open"  # open | acknowledged
    acked_at: Optional[str] = None
    acked_by: Optional[str] = None
    notes: List[Dict[str, Any]] = field(default_factory=list)
    evidence_status: str = "pending"  # pending | ready | partial | failed
    explanation: Optional[Dict[str, Any]] = None
    prev_hash: Optional[str] = None
    hash: Optional[str] = None

    @classmethod
    def create(
        cls,
        incident_type: str,
        severity: str,
        track_id: int,
        camera_id: str,
        confidence: float,
        duration_s: float,
        zone: Optional[str] = None,
        evidence_clip: Optional[str] = None,
        timestamp: Optional[str] = None,
        incident_id: Optional[str] = None,
        schema_version: str = "1.0",
        status: str = "open",
        acked_at: Optional[str] = None,
        acked_by: Optional[str] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
        evidence_status: str = "pending",
        explanation: Optional[Dict[str, Any]] = None,
        prev_hash: Optional[str] = None,
        hash: Optional[str] = None,
    ) -> Incident:
        """Helper to create an Incident with generated UUID and UTC ISO timestamp if not provided."""
        if incident_id is None:
            incident_id = str(uuid.uuid4())
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        return cls(
            incident_id=incident_id,
            timestamp=timestamp,
            camera_id=camera_id,
            type=incident_type,
            severity=severity,
            track_id=track_id,
            zone=zone,
            confidence=round(float(confidence), 3),
            duration_s=round(float(duration_s), 2),
            evidence_clip=evidence_clip,
            schema_version=schema_version,
            status=status,
            acked_at=acked_at,
            acked_by=acked_by,
            notes=notes if notes is not None else [],
            evidence_status=evidence_status,
            explanation=explanation,
            prev_hash=prev_hash,
            hash=hash,
        )

    @property
    def incident_type(self) -> str:
        return self.type

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Incident:
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
            notes=data.get("notes", []),
            evidence_status=data.get("evidence_status", "pending"),
            explanation=data.get("explanation"),
            prev_hash=data.get("prev_hash"),
            hash=data.get("hash"),
        )


@dataclass(frozen=True)
class IncidentEvent:
    """Transactional event payload published to the outbox and EventBus."""

    event_id: str
    event_type: str  # incident_created | incident_updated | incident_acked | incident_note_added
    incident_id: str
    timestamp: str
    payload: Dict[str, Any]

    @classmethod
    def create(
        cls,
        event_type: str,
        incident: Incident,
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> IncidentEvent:
        if event_id is None:
            event_id = str(uuid.uuid4())
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        return cls(
            event_id=event_id,
            event_type=event_type,
            incident_id=incident.incident_id,
            timestamp=timestamp,
            payload=incident.to_dict(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
