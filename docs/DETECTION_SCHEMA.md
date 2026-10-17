# SiteSentinel: Detection & Event Schemas

This document defines the canonical internal detection format emitted by PipeGen adapters, the incident notification event format, and the system health monitoring payload.

---

## 1. Canonical Detection Schema (`sentinel/detections`)

PipeGen outputs (whether transported via MQTT JSON messages or streamed to per-frame metadata JSON files) are parsed into this internal representation:

```json
{
  "camera_id": "cam-01",
  "frame_id": 1420,
  "ts": 1776435600.125,
  "frame": {
    "width": 1920,
    "height": 1080
  },
  "objects": [
    {
      "track_id": 12,
      "class": "person",
      "conf": 0.94,
      "bbox": [520.0, 310.0, 710.0, 890.0]
    },
    {
      "track_id": null,
      "class": "helmet",
      "conf": 0.91,
      "bbox": [570.0, 315.0, 660.0, 410.0]
    },
    {
      "track_id": null,
      "class": "vest",
      "conf": 0.88,
      "bbox": [545.0, 430.0, 685.0, 670.0]
    }
  ]
}
```

### Fields
- `camera_id` (string, required): Identifier of the capturing video source.
- `frame_id` (integer, required): Monotonically increasing sequence number from the decoder.
- `ts` (float, required): Frame presentation timestamp in epoch seconds (UTC). Used for deterministic replays.
- `frame` (object, required):
  - `width` (integer): Image width in pixels.
  - `height` (integer): Image height in pixels.
- `objects` (array of objects):
  - `track_id` (integer or null): Unique persistent tracking ID assigned by DeepStream NvDCF/ByteTrack (null for untracked PPE detections).
  - `class` (string): Canonical class name mapped via `config/sentinel.yaml` `class_map`: `"person"`, `"helmet"`, `"no_helmet"`, `"vest"`.
  - `conf` (float, 0.0 to 1.0): Detection confidence score.
  - `bbox` (array of 4 floats): Bounding box coordinates `[x1, y1, x2, y2]`.

---

## 2. Incident Event Schema (`sentinel/incidents`)

Published by the rule engine to MQTT QoS 1 and written to `logs/incidents.jsonl`:

```json
{
  "event": "incident_created",
  "incident_id": "e2a48b91-897c-4cb2-9d3e-953b1b46a1d8",
  "timestamp": "2026-10-17T15:30:00.125000+00:00",
  "camera_id": "cam-01",
  "type": "NO_HELMET",
  "severity": "MEDIUM",
  "track_id": 12,
  "zone": "walkway",
  "confidence": 0.925,
  "duration_s": 2.04,
  "evidence_clip": null
}
```

### Event Types
- `incident_created`: Published immediately when a violation window debounces and an incident is raised.
- `incident_updated`: Published when evidence clip generation completes and `evidence_clip` path is attached.
- `incident_acked`: Published when a safety officer acknowledges the incident from the dashboard or API.

---

## 3. System Health Schema (`sentinel/health`)

Published to `sentinel/health` (retained MQTT topic) at 1 Hz:

```json
{
  "component": "sentinel-engine",
  "status": "ok",
  "fps": 25.2,
  "latency_ms": 18.4,
  "engine_precision": "INT8",
  "gpu_util": 42.0,
  "gpu_power_w": 28.5,
  "mqtt": "up",
  "camera": "up",
  "ts": 1776435600.5
}
```

### Status Levels
- `"ok"`: FPS at target, camera up, MQTT connected, GPU healthy.
- `"degraded"`: FPS below 20, high latency, or pipeline dropouts.
- `"down"`: Camera lost, broker disconnected, or pipeline halted.
