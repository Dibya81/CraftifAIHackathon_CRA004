# SiteSentinel: Requirements Traceability Matrix

This document maps every Functional Requirement (FR-x) and Acceptance Criterion (AC-x) from `docs/PRD.md` to implementation code and verification tests or manual checks.

| ID | Requirement / Criterion | Implementation Component | Test / Verification Method | Status |
|---|---|---|---|---|
| FR-1 | Build pipeline through all 5 PipeGen stages | `pipegen/export/` | `HUMAN_TODO.md` §1 (Hardware/GUI) | Pending HW |
| FR-2 | Accept video file, USB camera or RTSP | `pipegen/export/run.sh`, `scripts/run_demo.sh` | Manual verification, CLI args | Pending HW |
| FR-3 | Compile model to TensorRT + keep speed report | `reports/speed_report_fp16.txt` | `HUMAN_TODO.md` §1 | Pending HW |
| FR-4 | Detect person, hard hat, head w/o hat, vest | `src/sentinel/models.py`, `pipegen/` | `tests/test_tracker_assoc.py` | Verified (Phase 1) |
| FR-5 | Track persons with stable IDs | `src/sentinel/models.py`, `pipegen/` | `tests/test_rules.py` | Verified (Phase 1) |
| FR-6 | Associate PPE boxes via head & torso overlap | `src/sentinel/tracker_assoc.py` | `tests/test_tracker_assoc.py` | Verified (Phase 1) |
| FR-7 | Polygon zones from JSON config & dashboard | `src/sentinel/zones.py` | `tests/test_zones.py` | Verified (Phase 1) |
| FR-8 | Incident for missing PPE > N seconds (debounce) | `src/sentinel/rules.py` | `tests/test_rules.py` | Verified (Phase 1) |
| FR-9 | Incident on restricted zone entry & danger dwell | `src/sentinel/rules.py` | `tests/test_rules.py` | Verified (Phase 1) |
| FR-10 | Debounce & cooldown per track violation | `src/sentinel/rules.py` | `tests/test_rules.py` | Verified (Phase 1) |
| FR-11 | Publish to MQTT & append to `incidents.jsonl` | `src/sentinel/incidents.py`, `mqtt_client.py` | `tests/test_incidents.py` | Verified (Phase 2) |
| FR-12 | Save 10s blurred evidence clip (5s pre, 5s post) | `src/sentinel/evidence.py` | `tests/test_evidence.py` | Verified (Phase 3) |
| FR-13 | Live dashboard view, feed, counts, hourly | `dashboard/` | Vitest + Component tests | Verified (Phase 5) |
| FR-14 | Offline evaluation harness (precision/recall/lat)| `eval/evaluate.py`, `tools/label_clip.py` | `tests/test_eval.py` | Verified (Phase 6) |
| FR-15 | FP16 vs INT8 speed, power, accuracy comparison | `tools/engine_report.py`, `reports/` | `tests/test_engine_report.py` | Verified (Phase 7) |
| FR-16 | Custom PPE detector with Edge MLOps parity | `models/` | `HUMAN_TODO.md` §4 | Pending HW |
| FR-17 | Telegram / webhook forwarding for HIGH incidents | `src/sentinel/notifications.py` | `tests/test_notifications.py` | Optional |
| AC-1 | 10 minutes live run on USB camera without crash | `tools/soak_test.py`, `tests/test_soak.py` | Soak verified (<1MB delta) / HW check pending |
| AC-2 | Person w/o helmet -> 1 incident in 3s; with -> 0 | `src/sentinel/rules.py` | `tests/test_rules.py` | Verified (Phase 1) |
| AC-3 | Restricted polygon -> 1 incident; re-entry -> 2 | `src/sentinel/rules.py` | `tests/test_rules.py` | Verified (Phase 1) |
| AC-4 | No stored clip contains legible face | `src/sentinel/evidence.py`, `tools/privacy_audit.py` | `tests/test_evidence.py` | Verified (Phase 3) |
| AC-5 | >= 85% recall, 80% precision on held-out clip | `eval/evaluate.py` | `eval/evaluate.py` run | Verified (Phase 6) |
| AC-6 | INT8 faster than FP16 with quantified accuracy | `tools/engine_report.py` | `make report` / report check | Verified (Phase 7) |
| AC-7 | Dashboard displays incident within 1s of MQTT | `dashboard/`, `src/sentinel/api.py` | Vitest + Component tests | Verified (Phase 5) |
