# Build prompt for Claude Code: SiteSentinel

Paste everything below the line into Claude Code from the project root. It also works as a `CLAUDE.md` if you copy it there.

---

You are the lead engineer on **SiteSentinel**, our entry for the Embedded SF (CraftifAI Physical AI) hackathon, **Track A: PipeGen**. We have about 8 weeks. The goal is to **win the track**, so every decision is judged against the hackathon judging criteria below. Work autonomously, but follow the working agreement exactly.

## 0. Read first
Before writing code, read in full: `README.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/diagrams/architecture.svg`, and every file under `config/`, `src/`, `scripts/`, `pipegen/`, `infra/`. These are the source of truth. If you find a conflict between them or a gap, list it, pick the most reasonable resolution, record it in `docs/DECISIONS.md` (decision, reason, date), and continue. Do not stop to ask unless you are blocked.

## 1. What we are building
A software-only safety intelligence system on top of a **PipeGen-generated DeepStream + TensorRT pipeline**:
- PipeGen detects person, hard hat, head-without-hat and high-vis vest, tracks people, blurs faces, and emits detections (MQTT + JSON + annotated RTSP).
- Our code (outside the PipeGen export) turns detections into **incidents** (NO_HELMET, NO_VEST, ZONE_INTRUSION, DANGER_DWELL), writes an append-only JSONL log and **face-blurred evidence clips**, publishes incidents over MQTT, serves a REST + WebSocket API, and drives a live dashboard.
- An **evaluation harness** reports precision, recall and alert latency per rule on a labelled clip.
- Tooling produces an **FP32/FP16/INT8 comparison report** from PipeGen's reports.

## 2. Judging criteria (optimize for these)
1. PipeGen must be **load-bearing**, not bolted on. Never modify `pipegen/export/`. Our code only consumes its outputs. The dashboard must visibly show PipeGen engine facts (precision, FPS, latency).
2. It must work **live on hardware**. A command that completes is not a system that works: show evidence.
3. Mandatory evidence: Pipeline IR graph, TensorRT speed report, actionable output (MQTT/JSON/clips), live run.
4. Bonus: Edge Optimization (INT8 vs FP16 with speed, power, accuracy).
5. Polish and reliability in a 4-minute live demo.

## 3. Hard rules
- **Never fabricate results.** Do not invent metrics, benchmark numbers, PipeGen outputs, screenshots, or "verified" claims. Anything that needs a GPU, the PipeGen GUI/CLI, a camera, or a human must be listed in `HUMAN_TODO.md` with exact steps, and the code that consumes its output must be built against a clearly labelled fixture or simulator.
- **Do not edit `pipegen/export/`** or commit generated binaries (engines, ONNX, videos, evidence).
- **Privacy:** no unblurred face frame may ever be written to disk. Evidence and dashboard video come only from the blurred stream. Add a config flag `privacy.require_blurred_source: true` and refuse to start evidence writing if the source is not marked blurred. Add a test for this.
- **Offline first:** no network calls at runtime.
- Keep dependencies minimal and pinned in `requirements.txt` and `dashboard/package.json`.
- Follow `docs/DESIGN.md` exactly for UI tokens, copy rules and accessibility.

## 4. Working agreement
- Work in the phases below, in order. After each phase: run all tests and linters, update docs where behavior changed, append a dated entry to `docs/PROGRESS.md` (what was done, what is verified, what is pending), and commit with a clear message (`phase-N: ...`). Initialize git if missing.
- Write tests first or alongside code. Every functional requirement FR-x and acceptance criterion AC-x in `docs/PRD.md` must map to at least one test or one documented manual check. Maintain `docs/TRACEABILITY.md` mapping FR/AC to code and tests.
- Prefer small, typed, well-named modules. Python 3.10+, type hints, `ruff` and `pytest`. Dashboard: Vite + React + TypeScript.
- When something is unknown about PipeGen's real output format, build an **adapter layer** (section 6) so only one file changes when we see the real output.
- Keep a `Makefile` with: `make install`, `make test`, `make lint`, `make sim` (run full stack on simulated detections), `make demo`, `make eval`, `make report`.

## 5. Phase plan

### Phase 0: Scaffolding (day 1)
- `pyproject.toml` or keep `requirements.txt`; add `ruff`, `pytest`, `mypy` (lenient). Create `Makefile`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TRACEABILITY.md`, `HUMAN_TODO.md`.
- Add typed config loading (pydantic) for `config/sentinel.yaml`, `config/rules.yaml`, `config/zones.json`, with validation errors that say exactly what to fix.
- Add structured logging (JSON lines to `logs/sentinel.log` plus readable console).

### Phase 1: Core domain logic (pure Python, no I/O)
Implement and unit test:
1. **Models** (`src/sentinel/models.py`): `Box`, `Detection(class, conf, box, track_id|None)`, `FrameMeta(ts, frame_id, camera_id, detections)`, `Incident` (as in PRD section 7).
2. **Zones** (`zones.py`): polygon zones (safe, restricted, danger) with `required_ppe`; test the person's **foot-point** (bottom-center of box) with shapely; support zone coordinates in the configured frame size and rescale if the frame size differs.
3. **PPE association** (`tracker_assoc.py`): for each person, helmet counts as worn if a helmet box overlaps the head region (top 0-25% of person box) with intersection-over-helmet-area at or above `min_overlap`; vest counts if a vest box overlaps the torso region (25-70%). A "head without helmet" detection inside the head region marks an explicit violation with higher confidence. Handle overlapping people (assign each PPE box to the best-matching person only).
4. **Rule engine** (`rules.py`): per-track state machine `OK -> VIOLATING(timer) -> INCIDENT_RAISED(cooldown) -> OK`. Rules: NO_HELMET, NO_VEST (use required PPE of the zone the person stands in, default zone otherwise), ZONE_INTRUSION (restricted entry, raised once per entry), DANGER_DWELL (dwell in danger zone above threshold, HIGH). Debounce with `min_duration_s`; one incident per continuous violation; re-alert only after `cooldown_s`; close lost tracks after 2 s; use frame timestamps (not wall clock) so replays are deterministic. Confidence of an incident = mean detection confidence over the violating window.
5. **Incident sink** (`incidents.py`): append-only `logs/incidents.jsonl` (fsync-safe), UUIDs, ISO-8601 UTC timestamps, severity mapping from `config/rules.yaml`.
Tests must cover: debounce edges, cooldown, track loss/reuse, overlapping people, zone boundary points, zone-specific PPE requirements, deterministic replay, and AC-2/AC-3 scenarios using synthetic frame sequences.

### Phase 2: Detection adapter, MQTT, simulator
- **Adapter** (`src/sentinel/adapters/pipegen.py`): converts PipeGen's detection payload to `FrameMeta`. Because the real format is unknown, define a documented internal schema in `docs/DETECTION_SCHEMA.md`, implement the adapter against it, and make the class mapping configurable in `config/sentinel.yaml` (`class_map`). Also implement a **JSON-file adapter** that tails PipeGen's JSON metadata files as an alternative to MQTT, selectable by config. Add `HUMAN_TODO.md` step: "Capture a real sample of PipeGen output, drop it in `tests/fixtures/pipegen_sample.*`, and adjust the adapter."
- **MQTT client** (`mqtt_client.py`): paho-mqtt v2, auto-reconnect with backoff, QoS 1 for incidents, QoS 0 for detections, retained `sentinel/health`. Topic names from config.
- **Simulator** (`tools/simulate.py`): generates realistic synthetic detection streams (walking persons with/without PPE, zone entries, track ID churn, occlusion dropouts, jitter) and publishes to MQTT at 25 FPS; also can write a synthetic annotated video with OpenCV so evidence and dashboard can be developed without a GPU. Include named scenarios: `compliant`, `no_helmet`, `restricted_entry`, `danger_dwell`, `crowd`, `flicker` (detections that flap, to test debounce).
- Integration test: simulator -> MQTT broker -> rule engine -> incident topic + JSONL, using a real Mosquitto from `infra/docker-compose.yml` (skip automatically if Docker is absent, and also provide an in-process fake broker for CI).

### Phase 3: Evidence and privacy
- **Frame source** (`evidence.py`): reads the blurred annotated RTSP stream (or video file) with OpenCV/FFmpeg into a ring buffer holding `pre_seconds` of frames; on incident, collects `post_seconds` more and writes an MP4 (H.264 if available) to `evidence/YYYY-MM-DD/<incident_id>.mp4` plus a JPEG thumbnail. Write asynchronously so the rule engine never blocks.
- Update the incident with `evidence_clip` and republish an `incident_updated` event.
- Enforce the privacy rule from section 3. Add a defense in depth: an optional secondary check that runs a lightweight face detector (OpenCV) on a sample of frames of each saved clip and logs a `PRIVACY_WARNING` health event if a legible face is found. Add an offline script `tools/privacy_audit.py` that scans `evidence/` and fails if any face is found; run it from `make test-privacy`.
- Handle stream drops: reconnect, mark clip as `partial` in metadata rather than failing.

### Phase 4: API
FastAPI (`api.py`) with:
- `GET /api/health`, `GET /api/incidents?limit&since&type&zone&severity`, `GET /api/incidents/{id}`, `POST /api/incidents/{id}/ack`, `POST /api/incidents/{id}/note`.
- `GET/PUT /api/zones` (validates polygons, writes `config/zones.json` atomically, hot-reloads the rule engine), `GET /api/zones/snapshot` (latest still frame for the zone editor).
- `GET /api/stats?window=` (counts per type, zone, hour; compliance percentage).
- `GET /api/system` (engine precision FP16/INT8, FPS, latency, GPU util via `nvidia-smi` if present, MQTT state, camera state, uptime) and `GET /api/system/engine-report` (serves the parsed PipeGen report comparison from `reports/engine_comparison.json`).
- `WS /ws/live` pushing incidents, health, and stats deltas.
- Static mount for `/evidence`. CORS for the dashboard dev server. Pydantic response models and OpenAPI docs.
- Tests with `httpx` and the WebSocket test client.

### Phase 5: Dashboard (follow `docs/DESIGN.md` strictly)
Vite + React + TypeScript, CSS variables for the design tokens (steel-900, concrete-100/50, signal-blue, hazard-orange, caution-amber, clear-green), Barlow Condensed + IBM Plex Sans (self-host the fonts under `dashboard/public/fonts` so it works offline).
Screens: Live view, Incident detail, Zone editor (draw/edit polygons on the snapshot, choose zone type and required PPE, save), Reports (compliance by zone/type/hour, CSV export), System (engine precision, FPS, latency, GPU power, FP16 vs INT8 table).
Requirements:
- Top health bar always visible: camera id, engine precision, FPS, MQTT status, GPU. Green/amber/orange states exactly as in DESIGN.md.
- Live annotated video: use an HTTP-friendly path (MJPEG proxy or HLS/WebRTC via a small relay; choose the simplest that works offline and document it). Zone overlays drawn on top, outline turns hazard-orange while a violation is active.
- Incident feed updates over the WebSocket with the single slide-in animation, severity shown by icon + label + color, ARIA live region, keyboard navigable, visible focus ring, reduced-motion respected.
- "Present" mode for the demo (large video, feed, health bar, no editor).
- Empty/error states use the copy rules in DESIGN.md.
- Responsive down to tablet; mobile shows the feed first.
- Component tests (Vitest + Testing Library) for the incident feed, health pill states, and zone editor geometry; one Playwright smoke test that runs against the simulator.

### Phase 6: Evaluation harness (this is our proof)
- Define the ground-truth format in `eval/README.md` (already sketched) and a small labelling helper `tools/label_clip.py` (OpenCV window: scrub video, press keys to mark violation start/end and type, save JSON).
- `eval/evaluate.py`: replay a clip's detections (from PipeGen JSON output or fixture) through the rule engine using **frame timestamps**, match incidents to ground-truth intervals (tolerance configurable), compute per-rule precision, recall, F1, mean/p95 alert latency, false-alarm rate per hour; write `reports/eval_<date>.json` and a readable `reports/eval_<date>.md` with a confusion summary and a list of the worst false positives/negatives with timestamps.
- Add a **threshold sweep** (`min_duration_s`, `min_overlap`, confidence) that outputs a table and recommends settings; never auto-apply them.
- Unit tests on the matcher with hand-built cases. AC-5 is checked here, using real data only; if only simulated data exists, the report must say "SIMULATED" in its header.

### Phase 7: Edge optimization reporting (bonus)
- `tools/engine_report.py`: ingest PipeGen's TensorRT speed reports and our accuracy runs for FP32/FP16/INT8 from a simple documented input file (`reports/engine_inputs.yaml`: FPS, latency, power, mAP, recall per precision, with the source of each number). Produce `reports/engine_comparison.json` and `.md` (table + short honest analysis of the trade-off, including where INT8 hurts, such as distant helmets). The API serves it and the System screen renders it.
- Add `HUMAN_TODO.md` steps for producing each number (which PipeGen screen, which command) and a calibration-set checklist (500+ frames, varied lighting/distance).

### Phase 8: Demo hardening
- `scripts/run_demo.sh`: starts Mosquitto, PipeGen run script (path from config), rule engine, evidence writer, API, dashboard; waits for health; prints URLs; clean shutdown on Ctrl-C. Add `--sim` (everything on simulator, no GPU) and `--file <video>` modes.
- Process supervision with restart and health events (`sentinel/health`), including camera-lost and pipeline-stalled detection (no detections for N seconds).
- Soak test script: run 30 minutes on the simulator with periodic faults (broker restart, camera drop) and assert no crash, bounded memory, and no lost incidents; produce `reports/soak_<date>.md`.
- Fixtures: `demo/` folder with a recorded fallback clip placeholder, the demo script from PRD section 13, and `demo/CHECKLIST.md` (pre-demo checks: GPU, camera index, broker, lighting, zone calibration, backup video, laptop power and display settings).

### Phase 9: Submission pack
- `tools/make_submission.py` collects: PRD, architecture doc and diagram, PipeGen requirement text, links/paths to Pipeline IR screenshot and TensorRT reports (placeholders if missing, flagged), evaluation report, engine comparison, sample incidents.jsonl, sample evidence clip, and generates `SUBMISSION.md` with the project description (problem, track, pipeline inputs/tasks/models/precision/outputs, bonuses claimed). It must list any missing evidence loudly instead of papering over it.
- Finalize `README.md` with a 5-minute quick start, screenshots placeholders, and the architecture diagram.

## 6. Interfaces to define precisely
- **Internal detection schema** (document in `docs/DETECTION_SCHEMA.md`): `{ "camera_id", "frame_id", "ts" (epoch seconds float), "frame": {"width","height"}, "objects": [{"track_id": int|null, "class": "person|helmet|no_helmet|vest", "conf": float, "bbox": [x1,y1,x2,y2]}] }`.
- **Incident event types** on `sentinel/incidents`: `incident_created`, `incident_updated` (evidence attached), `incident_acked`.
- **Health payload**: `{ "component", "status": "ok|degraded|down", "fps", "latency_ms", "engine_precision", "gpu_util", "gpu_power_w", "mqtt": "up|down", "camera": "up|down", "ts" }`.

## 7. Quality bar
- `make test` and `make lint` green before every commit. Test coverage for `src/sentinel` core logic at least 85%.
- No TODO stubs left in files that are claimed done in `docs/PROGRESS.md`.
- Deterministic replays: same input, same incidents.
- Clear error messages for misconfiguration and missing PipeGen output.
- Performance: rule engine must process 25 FPS with 20 simultaneous persons using under 15% of one CPU core on a laptop; add a benchmark test.

## 8. What to do when blocked
If a step needs the GPU, PipeGen, a camera, or a human decision: implement everything around it, add precise steps to `HUMAN_TODO.md` (what to run, what to capture, where to put the file, which test to rerun), and continue with the next phase. At the end of each phase, print the current contents of `HUMAN_TODO.md` so I can act on it.

## 9. First actions
1. Read the docs and code listed in section 0.
2. Write a short plan (max 25 lines) for Phase 0 and Phase 1, plus any conflicts or assumptions you found.
3. Execute Phase 0, then Phase 1, committing after each. Then continue through the phases without waiting for approval, stopping only at genuine blockers.
