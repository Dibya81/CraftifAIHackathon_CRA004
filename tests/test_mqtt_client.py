"""Unit tests for SentinelMQTTClient callbacks and publishing behavior."""

from unittest.mock import MagicMock

from sentinel.config import MqttConfig
from sentinel.models import Incident
from sentinel.mqtt_client import SentinelMQTTClient


def test_mqtt_callbacks_and_dispatch():
    cfg = MqttConfig(
        host="localhost",
        port=1883,
        detections_topic="sentinel/detections",
        incidents_topic="sentinel/incidents",
        health_topic="sentinel/health",
    )
    received = []

    def on_det(payload):
        received.append(payload)

    client = SentinelMQTTClient(cfg, client_id="test-client", on_detection_callback=on_det)

    # 1. Test _on_connect
    mock_inner_client = MagicMock()
    client._on_connect(mock_inner_client, None, None, 0)
    assert client.connected is True
    mock_inner_client.subscribe.assert_called_with("sentinel/detections", qos=0)

    # 2. Test _on_connect failure
    client._on_connect(mock_inner_client, None, None, 5)
    assert client.connected is False

    # 3. Test _on_message dispatch
    msg = MagicMock()
    msg.topic = "sentinel/detections"
    msg.payload = b'{"frame_id": 42, "ts": 12.3}'
    client._on_message(mock_inner_client, None, msg)
    assert len(received) == 1
    assert received[0]["frame_id"] == 42

    # 4. Test _on_disconnect
    client._on_disconnect(mock_inner_client, None, None, 1)
    assert client.connected is False


def test_mqtt_publishing():
    cfg = MqttConfig()
    client = SentinelMQTTClient(cfg)
    client.client = MagicMock()

    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=1,
        camera_id="cam-01",
        confidence=0.9,
        duration_s=2.0,
    )

    client.publish_incident(inc)
    assert client.client.publish.called

    client.publish_detection({"test": 123})
    assert client.client.publish.called

    client.publish_health({"status": "ok"})
    assert client.client.publish.called
