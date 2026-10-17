"""EventBus port for decoupled inter-service messaging."""

from __future__ import annotations

from typing import Any, Callable, Dict, Protocol

EventHandler = Callable[[str, Dict[str, Any]], None]


class EventBus(Protocol):
    """Protocol for event publishing and subscription."""

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Publishes an event payload to a topic."""
        ...

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Registers a callback for matching incoming messages."""
        ...

    def start(self) -> None:
        """Initializes client connections."""
        ...

    def stop(self) -> None:
        """Gracefully disconnects and shuts down client."""
        ...
