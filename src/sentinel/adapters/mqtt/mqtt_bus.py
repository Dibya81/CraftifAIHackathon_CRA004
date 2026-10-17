"""MQTT EventBus adapter implementing EventBus protocol with Paho v2 and LWT."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from paho.mqtt.client import CallbackAPIVersion, Client

from sentinel.config import MqttConfig
from sentinel.ports.event_bus import EventHandler

logger = logging.getLogger("sentinel.adapters.mqtt")


class MqttEventBus:
    """Production EventBus implementation using paho-mqtt v2 with exponential backoff and LWT."""

    def __init__(
        self,
        config: MqttConfig,
        client_id: str = "sentinel-bus",
        lwt_topic: Optional[str] = None,
        lwt_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config
        self.client_id = client_id
        self.connected = False
        self._subscriptions: List[Tuple[str, EventHandler]] = []

        self.client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Configure Last-Will-and-Testament (LWT)
        will_topic = lwt_topic or config.health_topic
        will_body = json.dumps(
            lwt_payload
            or {
                "component": client_id,
                "status": "down",
                "details": "Unexpected disconnect (LWT triggered)",
            }
        )
        self.client.will_set(will_topic, will_body, qos=1, retain=True)

    def _on_connect(
        self, client: Client, userdata: Any, flags: Any, rc: Any, properties: Any = None
    ) -> None:
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker at %s:%d", self.config.host, self.config.port)
            # Re-subscribe all registered topics
            for topic, _ in self._subscriptions:
                client.subscribe(topic, qos=1)
        else:
            self.connected = False
            logger.error("Failed to connect to MQTT broker, return code: %s", rc)

    def _on_disconnect(
        self, client: Client, userdata: Any, flags: Any, rc: Any, properties: Any = None
    ) -> None:
        self.connected = False
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection (rc=%s). Auto-reconnecting...", rc)
        else:
            logger.info("MQTT client disconnected cleanly.")

    def _on_message(self, client: Client, userdata: Any, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="replace")}

        for pattern, handler in self._subscriptions:
            if self._topic_matches(pattern, msg.topic):
                try:
                    handler(msg.topic, payload)
                except Exception as exc:
                    logger.error("Error in handler for %s: %s", msg.topic, exc)

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        raw = json.dumps(payload)
        info = self.client.publish(topic, raw, qos=qos, retain=retain)
        if qos > 0:
            info.wait_for_publish(timeout=2.0)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscriptions.append((topic, handler))
        if self.connected:
            self.client.subscribe(topic, qos=1)

    def start(self) -> None:
        try:
            self.client.connect_async(self.config.host, self.config.port, keepalive=60)
            self.client.loop_start()
        except Exception as exc:
            logger.warning("Could not connect to MQTT broker on startup: %s", exc)

    def stop(self) -> None:
        self.client.loop_stop()
        if self.connected:
            self.client.disconnect()

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        import fnmatch

        regex = pattern.replace("+", "[^/]+").replace("#", ".*")
        return bool(fnmatch.fnmatch(topic, regex))
