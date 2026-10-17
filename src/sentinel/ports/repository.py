"""Repository port for transactional incident persistence and query operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple

from sentinel.domain.models import Incident, IncidentEvent


class IncidentRepository(Protocol):
    """Protocol for incident storage and outbox transactions."""

    def save_incident(
        self,
        incident: Incident,
        outbox_event: Optional[IncidentEvent] = None,
    ) -> None:
        """Persists an incident and enqueues an outbox event atomically in a single transaction."""
        ...

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by its unique ID."""
        ...

    def list_incidents(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        since_iso: Optional[str] = None,
        until_iso: Optional[str] = None,
        incident_type: Optional[str] = None,
        zone: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[Incident], Optional[str]]:
        """Lists incidents matching filters with keyset pagination. Returns (items, next_cursor)."""
        ...

    def ack_incident(
        self,
        incident_id: str,
        acked_by: str = "safety-officer",
        note: Optional[str] = None,
        acked_at: Optional[str] = None,
    ) -> Optional[Incident]:
        """Acknowledges an incident and optionally adds a note in a single transaction."""
        ...

    def add_note(
        self,
        incident_id: str,
        note_text: str,
        author: str = "safety-officer",
        timestamp: Optional[str] = None,
    ) -> Optional[Incident]:
        """Appends an audit note to an incident."""
        ...

    def update_evidence(
        self,
        incident_id: str,
        clip_path: str,
        evidence_status: str = "ready",
    ) -> Optional[Incident]:
        """Updates the evidence clip path and status for an incident."""
        ...

    def get_pending_outbox_events(self, limit: int = 50) -> List[IncidentEvent]:
        """Fetches undelivered outbox events for publishing."""
        ...

    def mark_outbox_event_published(self, event_id: str) -> None:
        """Marks an outbox event as successfully dispatched."""
        ...

    def get_stats(self, window_hours: int = 24) -> Dict[str, Any]:
        """Computes aggregated safety metrics over the given time window."""
        ...
