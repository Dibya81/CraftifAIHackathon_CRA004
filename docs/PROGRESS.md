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
  - Test coverage: 31 passed tests, 89% total coverage across `src/sentinel` (models: 96%, tracker_assoc: 91%, zones: 97%, rules: 87%, incidents: 85%, config: 89%).
  - Code hygiene: `ruff check` and `mypy` pass with 0 errors.
- **What is pending**:
  - Phase 2: Detection adapter, MQTT client, simulator (`tools/simulate.py`), integration tests.
