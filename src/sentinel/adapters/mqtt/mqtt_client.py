"""MQTT client adapter for SiteSentinel using paho-mqtt v2.

Subscribes to PipeGen detections (QoS 0), publishes incidents (QoS 1),
and emits retained health payloads (sentinel/health). Handles auto-reconnect with backoff.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

from paho.mqtt.client import CallbackAPIVersion, Client

from sentinel.config import MqttConfig
from sentinel.domain.models import Incident

logger = logging.getLogger("sentinel.adapters.mqtt.client")


class SentinelMQTTClient:
    """Manages MQTT communication for SiteSentinel."""

    def __init__(
        self,
        config: MqttConfig,
        client_id: str = "sentinel-engine",
        on_detection_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.config: MqttConfig = config
        self.client_id: str = client_id
        self.on_detection_callback = on_detection_callback
        self.connected: bool = False

        self.client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client: Client, userdata: Any, flags: Any, rc: Any, properties: Any = None) -> None:
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker at %s:%d", self.config.host, self.config.port)
            client.subscribe(self.config.detections_topic, qos=0)
            logger.info("Subscribed to detections topic: %s (QoS 0)", self.config.detections_topic)
        else:
            self.connected = False
            logger.error("Failed to connect to MQTT broker, return code: %s", rc)

    def _on_disconnect(self, client: Client, userdata: Any, flags: Any, rc: Any, properties: Any = None) -> None:
        self.connected = False
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection (rc=%s). Auto-reconnecting...", rc)
        else:
            logger.info("MQTT client disconnected cleanly.")

    def _on_message(self, client: Client, userdata: Any, msg: Any) -> None:
        if msg.topic == self.config.detections_topic and self.on_detection_callback:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                self.on_detection_callback(payload)
            except Exception as e:
                logger.error("Error processing MQTT detection payload: %s", e)

    def connect(self) -> None:
        """Connect to the broker and start background network thread."""
        logger.info("Connecting to MQTT broker %s:%d...", self.config.host, self.config.port)
        self.client.connect(self.config.host, self.config.port, keepalive=60)
        self.client.loop_start()

    def disconnect(self) -> None:
        """Stop background network loop and disconnect."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.warning("Error during MQTT disconnect: %s", e)
        finally:
            self.connected = False

    def publish_incident(self, incident: Incident, event_type: str = "incident_created") -> None:
        """Publish an incident to sentinel/incidents at QoS 1."""
        payload = incident.to_dict()
        payload["event"] = event_type
        data_str = json.dumps(payload)
        info = self.client.publish(self.config.incidents_topic, data_str, qos=1)
        info.wait_for_publish(timeout=2.0)
        logger.info(
            "Published incident %s (%s) to %s (QoS 1)",
            incident.incident_id,
            incident.type,
            self.config.incidents_topic,
        )

    def publish_detection(self, detection_dict: Dict[str, Any]) -> None:
        """Publish a detection frame to sentinel/detections at QoS 0."""
        data_str = json.dumps(detection_dict)
        self.client.publish(self.config.detections_topic, data_str, qos=0)

    def publish_health(self, health_dict: Dict[str, Any]) -> None:
        """Publish system health to sentinel/health as retained message."""
        data_str = json.dumps(health_dict)
        self.client.publish(self.config.health_topic, data_str, qos=1, retain=True)


__all__ = ["SentinelMQTTClient"]
