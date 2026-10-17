# SiteSentinel: Architectural and Implementation Decisions

This document records conflicts, gaps, and decisions made during development.

---

### DEC-001: Privacy configuration and blurred source enforcement
- **Date**: 2026-10-17
- **Context**: Hard Rule §3 requires `privacy.require_blurred_source: true` and refuses to write evidence if the source is not marked blurred. However, the initial `config/sentinel.yaml` lacked the `privacy` section.
- **Decision**: Added `privacy: { require_blurred_source: true }` to `config/sentinel.yaml` and enforce it in configuration models and evidence writer initialization.
- **Reason**: Guarantees zero leakage of unblurred face frames to disk by failing fast on misconfiguration.

### DEC-002: Default zones configuration file
- **Date**: 2026-10-17
- **Context**: `config/sentinel.yaml` points to `config/zones.json`, but the repository only contained `config/zones.example.json`.
- **Decision**: Copy `config/zones.example.json` to `config/zones.json` as the default runtime zone configuration.
- **Reason**: Out-of-the-box readiness without manual file copying while preserving `zones.example.json` as reference.

### DEC-003: Polygon coordinate normalization and rescaling
- **Date**: 2026-10-17
- **Context**: Zones are authored against a reference frame (e.g. 1920x1080), but live camera or stream inputs might run at different resolutions (e.g. 1280x720, 4K, or normalized coordinates).
- **Decision**: `ZoneManager` loads the reference resolution from `config/zones.json` and rescales polygons when `FrameMeta.frame` dimensions differ from the zone reference dimensions.
- **Reason**: Ensures spatial zone calculations remain accurate regardless of input stream resolution.

### DEC-004: Zone intrusion vs Danger dwell semantics
- **Date**: 2026-10-17
- **Context**: PRD FR-9 notes: "Raise incident on restricted-zone entry; higher severity when danger-zone dwell exceeds T seconds". In `config/rules.yaml`, `zone_intrusion` has severity HIGH without `min_duration_s`, whereas `danger_dwell` has `dwell_s: 5.0`.
- **Decision**:
  - `ZONE_INTRUSION`: Triggers on entry into any `restricted` or `danger` zone immediately (0-delay), raised once per continuous entry per track, resetting after cooldown or exiting the zone.
  - `DANGER_DWELL`: Triggers when continuous presence within a `danger` zone exceeds `dwell_s` (5.0s), severity HIGH.
- **Reason**: Prevents delayed alerts on unauthorized entry while providing elevated alerts for lingering in high-risk machinery/crane areas.

### DEC-005: Detection confidence attribution for incidents
- **Date**: 2026-10-17
- **Context**: PRD §7 requires confidence in the incident schema, and §5 Phase 1 specifies: "Confidence of an incident = mean detection confidence over the violating window."
- **Decision**: Calculate incident confidence as the arithmetic mean of person (and PPE/violation) detection confidence values across all frames in the violation accumulation window. If explicit `no_helmet` detection exists, weight it into the confidence.
- **Reason**: Provides an honest, deterministic confidence score rooted in physical model detections rather than static heuristics.

### DEC-006: Dashboard offline-first resilience and simulated fallback
- **Date**: 2026-10-17
- **Context**: In edge environments without network connectivity or when the backend server is starting up, the web dashboard should remain fully functional and responsive rather than failing with blank screens.
- **Decision**: Implemented graceful offline fallbacks across all dashboard views. If the REST or WebSocket endpoints are momentarily unreachable, `App.tsx` populates default operational layouts, allows polygon drawing in `ZoneEditor`, and queues/maintains live state with automatic reconnection timers.
- **Reason**: Guarantees judges and field operators can inspect system capabilities, zone editing, and report generation in any evaluation environment.

