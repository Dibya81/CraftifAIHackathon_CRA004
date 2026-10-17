"""Core data models for SiteSentinel.

Re-exports pure domain models from sentinel.domain.models for backward compatibility.
"""

from __future__ import annotations

from sentinel.domain.models import (
    Box,
    Detection,
    EvidenceStatus,
    FrameDimensions,
    FrameMeta,
    Incident,
    IncidentEvent,
    IncidentEventType,
    IncidentStatus,
    IncidentType,
    Severity,
    Track,
)

__all__ = [
    "Box",
    "Detection",
    "EvidenceStatus",
    "FrameDimensions",
    "FrameMeta",
    "Incident",
    "IncidentEvent",
    "IncidentEventType",
    "IncidentStatus",
    "IncidentType",
    "Severity",
    "Track",
]
