# SiteSentinel: Development Progress Log

### 2026-10-17: Phase 0 - Scaffolding Completed
- **What was done**:
  - Reconnaissance of PRD, architecture, diagrams, design, and configs.
  - Initialized git repository.
  - Setup Python 3.11 virtual environment with `uv` and pinned dependencies.
  - Configured `pyproject.toml` and `Makefile` with `test`, `lint`, `format`, `sim`, `demo`, `eval`, `report`.
  - Authored `docs/DECISIONS.md`, `HUMAN_TODO.md`, and `docs/TRACEABILITY.md`.
  - Implemented typed Pydantic v2 configuration loaders for `sentinel.yaml`, `rules.yaml`, and `zones.json` with actionable error diagnostics.
  - Implemented structured logging in `src/sentinel/logging.py` (JSON lines file logging + formatted console).
  - Authored and verified unit tests in `tests/test_config.py` and `tests/test_logging.py`.
- **What is verified**:
  - `pytest`: 7 passing unit tests.
  - `ruff`: Clean check across `src` and `tests`.
  - `mypy`: 0 type errors across all 10 source files.
- **What is pending**:
  - Phase 1: Core domain logic (models, zones geometry, PPE tracker association, rule engine state machine, incident sink).

---

### 2026-10-17: Phase 1 - Core Domain Logic Completed
- **What was done**:
  - Implemented `src/sentinel/models.py`: `Box` geometry with sub-regions (head/torso), intersection over area (IoA), foot-point calculation; `Detection`, `FrameMeta`, and `Incident` schemas matching PRD §7.
  - Implemented `src/sentinel/zones.py`: `Zone` and `ZoneManager` with shapely polygon coverage checks, zone priorities (`danger` > `restricted` > `safe`), foot-point testing, and automatic coordinate rescaling between incoming frame resolution and configured zone frame size.
  - Implemented `src/sentinel/tracker_assoc.py`: Anatomical PPE association matching helmets to head region (top 0-25%) and vests to torso region (25-70%) at `min_overlap`; explicit `no_helmet` violation override with elevated confidence; greedy best-match assignment for overlapping people.
  - Implemented `src/sentinel/rules.py`: Deterministic state machines per track using frame timestamps (`ts`); debounced `NO_HELMET` and `NO_VEST` (`min_duration_s`); immediate single-shot `ZONE_INTRUSION` on restricted/danger entry; continuous `DANGER_DWELL` alerts; lost track purging after 2.0s; cooldown gating before re-alerts.
  - Implemented `src/sentinel/incidents.py`: `IncidentSink` with thread-safe, append-only, fsync-durable logging to `logs/incidents.jsonl` with filtering and clip-path update helpers.
  - Added full test suite in `tests/test_models.py`, `tests/test_zones.py`, `tests/test_tracker_assoc.py`, `tests/test_rules.py`, `tests/test_incidents.py`, and `tests/test_benchmark.py`.
- **What is verified**:
  - Acceptance Criteria AC-2 (`NO_HELMET` fires once in 3s; compliant person fires 0).
  - Acceptance Criteria AC-3 (`ZONE_INTRUSION` fires once; re-entry after cooldown fires second).
  - Benchmark performance: processed 500 frames with 20 simultaneous persons in 0.317s (0.63 ms/frame, 1578 FPS), well below the 6.0 ms/frame (15% single-core) budget.
  - Test coverage: 31 passed tests, 89% total coverage across `src/sentinel`.
  - Code hygiene: `ruff check` and `mypy` pass with 0 errors.
- **What is pending**:
  - Phase 2: Detection adapter, MQTT client, simulator (`tools/simulate.py`), integration tests.

---

### 2026-10-17: Phase 2 - Detection Adapter, MQTT, and Simulator Completed
- **What was done**:
  - Documented canonical internal detection schema, incident event lifecycle (`incident_created`, `incident_updated`, `incident_acked`), and 1 Hz system health monitoring payload in `docs/DETECTION_SCHEMA.md`.
  - Implemented `src/sentinel/adapters/pipegen.py`: `PipeGenAdapter` with configurable class mapping (`class_map`), numeric class ID parsing, and flexible detection structure ingestion; and `JsonFileMetadataTailer` for tailing JSON metadata files.
  - Implemented `src/sentinel/mqtt_client.py`: `SentinelMQTTClient` utilizing `paho-mqtt` v2 with exponential backoff auto-reconnect, QoS 0 detection subscriptions, QoS 1 incident notifications, and retained health heartbeats.
  - Implemented `tools/simulate.py`: Multi-scenario synthetic detection stream simulator (`compliant`, `no_helmet`, `restricted_entry`, `danger_dwell`, `crowd`, `flicker`) with real-time 25 FPS pacing, MQTT broadcasting, and synthetic OpenCV video rendering with zone outlines and privacy face-blurring.
  - Created sample detection fixture in `tests/fixtures/pipegen_sample.json`.
  - Authored unit and integration test suites: `tests/test_pipegen_adapter.py`, `tests/test_mqtt_client.py`, `tests/test_simulator.py`, and `tests/test_integration_mqtt.py`.
- **What is verified**:
  - End-to-end integration: synthetic scenario streaming -> adapter parsing -> rule engine state machine -> incident sink durable JSONL commit + MQTT publish.
  - Test coverage: 39 passed tests across the suite, 88% overall test coverage in `src/sentinel`.
  - Code hygiene: `ruff` and `mypy` clean across all 13 source files.
- **What is pending**:
  - Phase 3: Evidence writer with ring buffer and privacy verification (`evidence.py`, `tools/privacy_audit.py`).

---

### 2026-10-17: Phase 3 - Evidence & Privacy Completed
- **What was done**:
  - Implemented `src/sentinel/evidence.py`: Thread-safe `RingBuffer` holding `pre_seconds` frames; asynchronous `EvidenceWriter` with `ThreadPoolExecutor` worker pool saving 10s MP4 evidence clips (`evidence/YYYY-MM-DD/<incident_id>.mp4`) and high-contrast JPEG thumbnails (`.jpg`).
  - Strict Privacy Policy Enforcement: Hard rule enforced at initialization — `EvidenceWriter` refuses to start or persist any frames if `privacy.require_blurred_source` is True and the stream is not certified blurred (`PrivacyViolationError`).
  - Implemented `tools/privacy_audit.py`: Automated scanning tool that inspects all saved MP4 clips and thumbnails using dual face-detection and skin/sharpness gradient texture analysis; fails with exit code 1 if any legible face is found.
  - Integrated `make test-privacy` target in `Makefile`.
  - Authored tests in `tests/test_evidence.py` verifying privacy enforcement, ring buffer rollover, asynchronous clip and thumbnail creation, and privacy audit passing.
- **What is verified**:
  - Functional Requirement FR-12 (Save 10s blurred evidence clip: 5s pre, 5s post).
  - Acceptance Criterion AC-4 (No stored clip contains legible face; verified via `tools/privacy_audit.py`).
  - Test coverage: 42 passed tests, 86% total coverage across `src/sentinel`.
  - Code hygiene: `ruff` and `mypy` pass with 0 errors across all 13 source files.
- **What is pending**:
  - Phase 4: FastAPI REST & WebSocket service (`src/sentinel/api.py`).

---

### 2026-10-17: Phase 4 - FastAPI Service Completed
- **What was done**:
  - Implemented `src/sentinel/api.py`: FastAPI application serving REST endpoints:
    - `GET /api/health`: Uptime, camera, MQTT, FP16/INT8 engine precision, FPS, latency, and GPU telemetry via `nvidia-smi`.
    - `GET /api/incidents`: Queryable incident log with filtering (limit, since, type, zone, severity) and acknowledgment/note statuses.
    - `GET /api/incidents/{id}`, `POST /api/incidents/{id}/ack`, and `POST /api/incidents/{id}/note`.
    - `GET /api/zones` and `PUT /api/zones`: Atomic polygon validation and hot-reloading of `config/zones.json`.
    - `GET /api/zones/snapshot`: Serves latest still frame (JPEG) for zone editor polygon authoring.
    - `GET /api/stats`: Aggregated metrics (type, zone, severity, hourly breakdown, compliance %).
    - `GET /api/system` and `GET /api/system/engine-report`: PipeGen engine speed report telemetry.
    - `WS /ws/live`: Real-time WebSocket pushing initial state, newly raised incidents, ack events, zone hot-reloads, and health heartbeats.
    - Static file mount at `/evidence` for clips and thumbnails.
    - Global CORS middleware for dashboard dev server.
  - Authored full test suite in `tests/test_api.py` covering health, incidents CRUD, acks, notes, zone updates, snapshot, stats, and WebSocket communication.
- **What is verified**:
  - 47 total passed tests, 86% total test coverage across `src/sentinel` (`api.py`: 85%).
  - Code hygiene: `ruff` and `mypy` clean across all 13 source files.
- **What is pending**:
  - Phase 5: Dashboard (Vite + React + TypeScript matching `docs/DESIGN.md` strictly).

---

### 2026-10-17: Phase 5 - Dashboard Completed
- **What was done**:
  - Initialized and configured Vite + React 18 + TypeScript SPA under `dashboard/`.
  - Implemented design system in `dashboard/src/index.css` strictly adhering to `docs/DESIGN.md`:
    - Industrial control room palette (`steel-900`, `concrete-100`, `concrete-50`, `signal-blue`, `hazard-orange`, `caution-amber`, `clear-green`).
    - Typography rules (Barlow Condensed headings, IBM Plex Sans body, tabular numerals).
    - Accessibility tokens (high-contrast ratios, focus rings, reduced motion support).
  - Implemented modular component library:
    - `HealthBar`: Universal header displaying brand, camera ID, PipeGen engine precision badge (INT8/FP16), FPS/latency, health status pill, camera lost warning banner, and "Present" mode toggle.
    - `IncidentFeed`: ARIA live region stream with formatted names ("No helmet", "Zone entry", "Danger-zone dwell"), severity badges with icons, relative timestamps, blurred clip indicators, and active selection states.
    - `VideoPlayerWithZones`: Live video viewport with SVG zone overlay layer; safe/restricted/danger polygons; dynamic outline color change to hazard-orange with 4px stroke on active violations; live privacy watermark.
    - `ZoneEditor`: Interactive polygon drawing canvas over camera snapshot frame; click-to-plot vertices, undo point, zone ID and type configuration, required PPE toggles, atomic `PUT /api/zones` updates, and "Zone saved" toast feedback.
    - `IncidentDetailModal`: Modal with blurred MP4 evidence playback, timeline/duration facts, officer acknowledgement with optional comment, and timestamped audit note thread.
    - `ReportsView`: Overall site compliance percentage card, zone breakdown, violation type share, hourly distribution bar chart, and CSV export action.
    - `SystemView`: Live hardware telemetry facts (FPS, latency, GPU power & utilization), PipeGen zero-copy pipeline callout, and Jetson Orin FP32 vs FP16 vs INT8 comparison table.
    - `TodayByZoneAndHourly`: Live view lower-deck cards for zone distribution and hourly trends.
    - `App`: State coordinator with auto-reconnecting WebSocket (`/ws/live`), REST API polling fallback, and present-mode judge view.
  - Implemented component test suite using Vitest and React Testing Library:
    - `src/test/HealthBar.test.tsx`: System state, engine precision, camera lost banner, navigation, present mode.
    - `src/test/IncidentFeed.test.tsx`: Design copy formatting, empty state, row rendering, selection.
    - `src/test/ZoneEditor.test.tsx`: Zone list rendering, drawing mode switch.
    - `src/test/VideoPlayerWithZones.test.tsx`: Color calculations, SVG rendering, zone toggle.
- **What is verified**:
  - Vitest: 11 passed tests across 4 test suites in `dashboard/`.
  - Production build: `npm --prefix dashboard run build` succeeds with zero TypeScript errors.
  - Full project test suite: `make test` runs 47 Python tests + 11 Dashboard tests (58 total passed).
  - Code hygiene: `make lint` clean across all backend files; frontend 100% type-checked.
- **What is pending**:
  - Phase 6: Evaluation harness (`tools/label_clip.py`, `eval/evaluate.py`, precision/recall/F1/latency matcher, threshold sweeps).

