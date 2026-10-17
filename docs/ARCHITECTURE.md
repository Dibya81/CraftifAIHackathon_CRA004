# SiteSentinel: Architecture

Diagram: `diagrams/architecture.svg` (PNG copy alongside).

## 1. Principle
PipeGen is the perception engine and the system of record for detections. SiteSentinel adds meaning (rules), evidence, and presentation on top of PipeGen's outputs. The PipeGen export folder is never modified; all custom logic lives outside it and talks to it only through MQTT, JSON and RTSP.

## 2. Components
| Component | Tech | Responsibility |
|---|---|---|
| Video source | USB camera / RTSP / file | Frames into the pipeline |
| PipeGen pipeline | DeepStream + TensorRT (generated) | Decode, detect person/PPE, track, blur faces, emit detections |
| Edge MLOps | Training + ONNX export | Custom PPE model, parity check, hand-off to PipeGen |
| MQTT broker | Mosquitto | Message bus between pipeline, rule engine, dashboard |
| Rule engine | Python | PPE association, zone geometry, per-track state machines, debounce |
| Evidence writer | Python + OpenCV | Rolling buffer of blurred frames, 10 s clips per incident |
| Incident store | JSONL files + evidence folder | Append-only log and clips |
| API | FastAPI + WebSocket | Incidents, zones, stats, live push, health |
| Dashboard | Web (React or plain HTML) | Live view, feed, zone editor, stats, system health |
| Evaluation harness | Python | Replays a labelled clip, computes precision, recall, latency |

## 3. Data flow
1. Camera frames enter the PipeGen pipeline (selected at run time).
2. The detector (TensorRT) outputs person, helmet, head-without-helmet and vest boxes; the tracker assigns IDs.
3. A face-blur branch produces a blurred stream used for RTSP output and evidence.
4. Per-frame metadata is published to `sentinel/detections` (and saved as JSON).
5. The rule engine consumes detections, associates PPE to persons, tests foot-points against zones, updates per-track state, and emits incidents.
6. Incidents go to `sentinel/incidents`, `logs/incidents.jsonl`, and trigger the evidence writer.
7. The API serves incidents, stats and a WebSocket push; the dashboard renders them alongside the annotated RTSP stream.
8. System health (FPS, GPU use, engine precision, MQTT status) is published to `sentinel/health`.

## 4. MQTT topics
| Topic | Producer | Consumer | Payload |
|---|---|---|---|
| `sentinel/detections` | PipeGen pipeline | Rule engine | Frame metadata (boxes, classes, track IDs, timestamp) |
| `sentinel/incidents` | Rule engine | API, external clients | Incident JSON (see PRD section 7) |
| `sentinel/health` | All services | API, dashboard | FPS, latency, GPU, precision, status |

## 5. Rule engine design
- Association: for each person box, PPE boxes with overlap above `min_overlap` in the head region (helmet) or torso region (vest) count as worn.
- Zones: polygon test on the person's foot-point (bottom center of the box); zone type decides required PPE and severity.
- State machine per track: OK, VIOLATING (timer running), INCIDENT_RAISED (cooldown), then back to OK when compliant or the track is lost.
- Debounce: a violation must persist for `min_duration_s`; one incident per continuous violation; re-alert only after `cooldown_s`.
- Lost tracks: tracks missing for more than 2 s are closed so IDs are not reused in state.

## 6. Privacy design
Face blur is a node inside the PipeGen pipeline. Evidence and the dashboard video only ever read the blurred stream. The raw stream is never persisted.

## 7. Deployment
Single NVIDIA GPU laptop (x86-64 Linux, X11 session). Mosquitto runs in Docker; the pipeline, rule engine and API run as local processes via `scripts/run_demo.sh`. Videos live under `/home` as PipeGen requires.

## 8. Failure handling
- Camera disconnect: pipeline health event, dashboard banner, auto-reconnect.
- MQTT drop: rule engine reconnects and resumes; the incident log is the source of truth.
- Rule engine crash: supervised restart; per-track state is rebuilt from new detections.

## 9. Repo layout
```
sitesentinel/
  README.md
  docs/            PRD.md, DESIGN.md, ARCHITECTURE.md, diagrams/
  pipegen/         requirement.md, export/ (untouched PipeGen output)
  models/          train/, onnx/, engines/, calibration/
  data/            raw/, labelled/, test_clips/
  src/sentinel/    config, mqtt_client, zones, tracker_assoc, rules, incidents, evidence, api
  dashboard/       src/, public/
  config/          sentinel.yaml, rules.yaml, zones.example.json
  eval/            evaluate.py
  tests/
  scripts/         run_demo.sh, record_clip.sh
  infra/           docker-compose.yml, mosquitto.conf
  evidence/  logs/  reports/
```
