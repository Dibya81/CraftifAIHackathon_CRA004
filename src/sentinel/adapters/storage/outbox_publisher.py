"""Transactional outbox publisher draining events to the EventBus."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from sentinel.ports.event_bus import EventBus
from sentinel.ports.repository import IncidentRepository

logger = logging.getLogger("sentinel.storage.outbox")


def drain_outbox(
    repository: IncidentRepository,
    event_bus: EventBus,
    topic: str = "sentinel/incidents",
    batch_size: int = 50,
) -> int:
    """Dispatches pending outbox events to the EventBus and marks them published.

    Returns the count of successfully dispatched events.
    """
    events = repository.get_pending_outbox_events(limit=batch_size)
    dispatched = 0

    for event in events:
        try:
            # Publish event payload with QoS 1
            event_bus.publish(topic=topic, payload=event.to_dict(), qos=1)
            repository.mark_outbox_event_published(event.event_id)
            dispatched += 1
        except Exception as exc:
            logger.warning("Failed to dispatch outbox event %s: %s", event.event_id, exc)
            break

    return dispatched


class OutboxPublisherWorker:
    """Background supervisor thread that drains the outbox continuously with backoff."""

    def __init__(
        self,
        repository: IncidentRepository,
        event_bus: EventBus,
        topic: str = "sentinel/incidents",
        poll_interval_s: float = 0.5,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus
        self.topic = topic
        self.poll_interval_s = poll_interval_s
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="outbox-publisher")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def trigger_drain(self) -> int:
        """Immediate drain trigger."""
        return drain_outbox(self.repository, self.event_bus, self.topic)

    def _run_loop(self) -> None:
        while self._running:
            try:
                drain_outbox(self.repository, self.event_bus, self.topic)
            except Exception as exc:
                logger.error("Error in outbox publisher loop: %s", exc)
            time.sleep(self.poll_interval_s)
