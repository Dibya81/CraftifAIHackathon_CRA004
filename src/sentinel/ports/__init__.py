"""Ports package exposing domain-adjacent interfaces and protocols."""

from sentinel.ports.clock import Clock, InjectedClock, SystemClock
from sentinel.ports.event_bus import EventBus, EventHandler
from sentinel.ports.evidence_store import EvidenceStore
from sentinel.ports.repository import IncidentRepository
from sentinel.ports.system_probe import SystemProbe

__all__ = [
    "Clock",
    "InjectedClock",
    "SystemClock",
    "EventBus",
    "EventHandler",
    "EvidenceStore",
    "IncidentRepository",
    "SystemProbe",
]
