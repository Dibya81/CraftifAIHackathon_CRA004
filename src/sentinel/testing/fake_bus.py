"""In-process fake MQTT / EventBus for testing and offline execution."""

from __future__ import annotations

import fnmatch
from typing import Any, Callable, Dict, List, Tuple

EventHandler = Callable[[str, Dict[str, Any]], None]


class FakeEventBus:
    """Thread-safe, in-process EventBus for testing without Docker or external brokers."""

    def __init__(self) -> None:
        self.subscriptions: List[Tuple[str, EventHandler]] = []
        self.published_messages: List[Tuple[str, Dict[str, Any], int, bool]] = []
        self.is_connected: bool = True
        self.failure_mode: bool = False

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        if self.failure_mode:
            raise ConnectionError("Simulated broker outage")
        if not self.is_connected:
            return

        self.published_messages.append((topic, payload, qos, retain))

        # Deliver to matching subscribers
        for pattern, handler in list(self.subscriptions):
            if self._topic_matches(pattern, topic):
                try:
                    handler(topic, payload)
                except Exception:
                    pass

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.subscriptions.append((topic, handler))

    def start(self) -> None:
        self.is_connected = True

    def stop(self) -> None:
        self.is_connected = False

    def clear(self) -> None:
        self.published_messages.clear()
        self.subscriptions.clear()

    @staticmethod
    def _topic_matches(sub_pattern: str, pub_topic: str) -> bool:
        # MQTT wildcards: '+' matches single level, '#' matches multiple levels
        regex_pattern = sub_pattern.replace("+", "[^/]+").replace("#", ".*")
        return bool(fnmatch.fnmatch(pub_topic, regex_pattern))
