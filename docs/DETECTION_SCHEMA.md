# SiteSentinel: Detection & Event Schemas

This document defines the supported input perception formats accepted by the SiteSentinel adapter, the incident notification event format, and the system health monitoring payload.

> **Notice:** The external schemas below are assumed, to be confirmed against a real PipeGen sample during physical booth check-in. The adapter auto-detects and supports all variants behind a unified configuration interface (`sentinel doctor --payload <sample.json>`).

---

## 1. Supported Input Formats

### Format A: Canonical Schema (Default)
*(Assumed, to be confirmed against a real PipeGen sample)*

Emitted by standard MQTT JSON publishers or simulator:

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

### Format B: DeepStream nvmsgconv Object-Array Schema
*(Assumed, to be confirmed against a real PipeGen sample)*

Standard NVIDIA DeepStream `nvmsgconv` payload with nested object dictionaries and bounding box rects:

```json
{
  "version": "4.0",
  "id": "1420",
  "@timestamp": "2026-10-17T15:30:00.125Z",
  "sensorId": "cam-01",
  "sensor": {
    "id": "cam-01",
    "type": "Camera"
  },
  "objects": [
    {
      "object": {
        "id": "12",
        "type": "person",
        "confidence": 0.94,
        "bbox": {
          "topleftx": 520.0,
          "toplefty": 310.0,
          "bottomrightx": 710.0,
          "bottomrighty": 890.0
        }
      }
    },
    {
      "object": {
        "id": "-1",
        "type": "hard_hat",
        "confidence": 0.91,
        "bbox": {
          "left": 570.0,
          "top": 315.0,
          "width": 90.0,
          "height": 95.0
        }
      }
    }
  ]
}
```

### Format C: DeepStream Minimal Pipe-Delimited Schema
*(Assumed, to be confirmed against a real PipeGen sample)*

Low-overhead pipe-delimited payload serialization used in high-throughput embedded streaming:

**Variant C1 (JSON wrapper with pipe items):**
```json
{
  "version": "1.0",
  "sensorId": "cam-01",
  "frameId": 1420,
  "timestamp": 1776435600.125,
  "objects": [
    "12|0|520.0|310.0|190.0|580.0|0.94",
    "-1|1|570.0|315.0|90.0|95.0|0.91"
  ]
}
```
Field format: `track_id|class_id|x|y|w|h|conf` (or `x1|y1|x2|y2|conf`).

**Variant C2 (Raw string line per frame):**
```text
1420|cam-01|1776435600.125|12|0|520.0|310.0|190.0|580.0|0.94#-1|1|570.0|315.0|90.0|95.0|0.91
```

### Format D: NDJSON & File-Tailed Stream
*(Assumed, to be confirmed against a real PipeGen sample)*

Per-frame JSON metadata files appended line-by-line or tailed using `JsonFileMetadataTailer`. Captured directly using `tools/capture_stream.py`.

---

## 2. Adapter Configuration Parameters (`config/sentinel.yaml`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `adapter.format` | string | `auto` | Parser selection (`auto`, `canonical`, `deepstream_array`, `deepstream_pipe`, `ndjson`) |
| `adapter.bbox_format` | string | `xyxy` | Bounding box coordinate convention (`xyxy` or `xywh`) |
| `adapter.bbox_normalized` | boolean | `false` | Set `true` if coordinates are normalized `[0.0, 1.0]` |
| `adapter.timestamp_format`| string | `epoch` | Timestamp format (`epoch`, `iso`, `pts_fps`) |
| `adapter.fps` | float | `25.0` | Frame rate used when calculating timestamps from frame sequence numbers |
| `class_map` | mapping | Built-in | Maps integer IDs or external detector strings to canonical classes (`person`, `helmet`, `no_helmet`, `vest`) |

---

## 3. Incident Event Schema (`sentinel/incidents`)

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

---

## 4. System Health Schema (`sentinel/health`)

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
