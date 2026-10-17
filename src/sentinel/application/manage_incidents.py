"""Use cases for managing safety incidents: acknowledgement, notes, and queries."""

from __future__ import annotations

from typing import List, Optional, Tuple

from sentinel.domain.models import Incident
from sentinel.ports.event_bus import EventBus
from sentinel.ports.repository import IncidentRepository


class ManageIncidentsUseCase:
    """Orchestrates incident queries, acknowledgements, and audit notes."""

    def __init__(
        self,
        repository: IncidentRepository,
        event_bus: Optional[EventBus] = None,
        incidents_topic: str = "sentinel/incidents",
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus
        self.incidents_topic = incidents_topic

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.repository.get_incident(incident_id)

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
        return self.repository.list_incidents(
            limit=limit,
            cursor=cursor,
            since_iso=since_iso,
            until_iso=until_iso,
            incident_type=incident_type,
            zone=zone,
            severity=severity,
            status=status,
            search_query=search_query,
        )

    def acknowledge_incident(
        self,
        incident_id: str,
        acked_by: str = "safety-officer",
        note: Optional[str] = None,
    ) -> Optional[Incident]:
        updated = self.repository.ack_incident(incident_id, acked_by=acked_by, note=note)
        if updated and self.event_bus:
            from sentinel.adapters.storage.outbox_publisher import drain_outbox

            drain_outbox(self.repository, self.event_bus, topic=self.incidents_topic)
        return updated

    def add_incident_note(
        self,
        incident_id: str,
        note_text: str,
        author: str = "safety-officer",
    ) -> Optional[Incident]:
        updated = self.repository.add_note(incident_id, note_text=note_text, author=author)
        if updated and self.event_bus:
            from sentinel.adapters.storage.outbox_publisher import drain_outbox

            drain_outbox(self.repository, self.event_bus, topic=self.incidents_topic)
        return updated
