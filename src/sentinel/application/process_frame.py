"""Use case: ProcessFrame orchestrates frame evaluation, incident recording, and outbox publication."""

from __future__ import annotations

import logging
from typing import List, Optional

from sentinel.adapters.storage.outbox_publisher import drain_outbox
from sentinel.domain.models import FrameMeta, Incident, IncidentEvent, IncidentEventType
from sentinel.domain.rules import RuleEngine
from sentinel.ports.event_bus import EventBus
from sentinel.ports.repository import IncidentRepository

logger = logging.getLogger("sentinel.application.process_frame")


class ProcessFrameUseCase:
    """Consumes parsed detection frames, evaluates safety rules, persists incidents, and drains the outbox."""

    def __init__(
        self,
        rule_engine: RuleEngine,
        repository: IncidentRepository,
        event_bus: Optional[EventBus] = None,
        incidents_topic: str = "sentinel/incidents",
    ) -> None:
        self.rule_engine = rule_engine
        self.repository = repository
        self.event_bus = event_bus
        self.incidents_topic = incidents_topic

    def execute(self, frame: FrameMeta) -> List[Incident]:
        """Evaluates a single frame and persists any newly raised incidents."""
        raised = self.rule_engine.process_frame(frame)

        for incident in raised:
            event = IncidentEvent.create(
                event_type=IncidentEventType.INCIDENT_CREATED.value,
                incident=incident,
            )
            # Atomically commit to SQLite and enqueues outbox event, and fsync to JSONL
            self.repository.save_incident(incident=incident, outbox_event=event)
            logger.info(
                "Raised %s incident for track %d in %s",
                incident.type,
                incident.track_id,
                incident.zone,
            )

        # Trigger immediate outbox drain if EventBus is attached
        if raised and self.event_bus is not None:
            drain_outbox(self.repository, self.event_bus, topic=self.incidents_topic)

        return raised
