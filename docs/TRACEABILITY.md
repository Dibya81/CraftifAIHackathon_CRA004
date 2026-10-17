# SiteSentinel: Requirements & Test Traceability Matrix

This document maps every Functional Requirement (FR-x), Acceptance Criterion (AC-x), and Non-Functional Requirement (NFR-x) from `docs/PRD.md` to hexagonal architecture modules and automated test cases (TC-01 to TC-30).

| ID | Requirement / Criterion | Implementation Component | Test Case / Verification Method | Status |
|---|---|---|---|---|
| FR-1 | Build pipeline through all 5 PipeGen stages | `pipegen/export/` | TC-03 (`scripts/verify_hardware.sh`, `HUMAN_TODO.md` §1) | Pending HW |
| FR-2 | Accept video file, USB camera or RTSP | `pipegen/export/run.sh`, `scripts/run_demo.sh` | TC-29 (Manual verification, CLI args) | Pending HW |
| FR-3 | Compile model to TensorRT + keep speed report | `reports/speed_report_fp16.txt` | TC-02, TC-23 (`tools/engine_report.py`) | Verified |
| FR-4 | Detect person, hard hat, head w/o hat, vest | `src/sentinel/domain/models.py`, `pipegen/` | TC-06, TC-09 (`tests/test_models.py`, `test_tracker_assoc.py`) | Verified |
| FR-5 | Track persons with stable IDs | `src/sentinel/domain/rules.py` | TC-12, TC-13 (`tests/test_rules.py`, `test_property_rules.py`) | Verified |
| FR-6 | Associate PPE boxes via head & torso overlap | `src/sentinel/domain/association.py` | TC-09, TC-10, TC-11 (`tests/test_tracker_assoc.py`) | Verified |
| FR-7 | Polygon zones from JSON config & dashboard | `src/sentinel/domain/zones.py` | TC-07, TC-08 (`tests/test_zones.py`) | Verified |
| FR-8 | Incident for missing PPE > N seconds (debounce) | `src/sentinel/domain/rules.py` | TC-12, TC-25 (`tests/test_rules.py`, `tests/perf/test_benchmarks.py`) | Verified |
| FR-9 | Incident on restricted zone entry & danger dwell | `src/sentinel/domain/rules.py` | TC-14, TC-15 (`tests/test_rules.py`) | Verified |
| FR-10 | Debounce & cooldown per track violation | `src/sentinel/domain/rules.py` | TC-12, TC-13 (`tests/test_property_rules.py`, `test_rules.py`) | Verified |
| FR-11 | SQLite WAL + transactional outbox + JSONL audit log | `src/sentinel/adapters/storage/` | TC-16, TC-27 (`tests/test_storage.py`, `test_integration_mqtt.py`) | Verified |
| FR-12 | Save 10s blurred evidence clip (5s pre, 5s post) | `src/sentinel/adapters/video/clip_writer.py` | TC-17 (`tests/test_evidence.py`) | Verified |
| FR-13 | Live dashboard view, feed, counts, hourly | `dashboard/` | Vitest + Frontend component tests | Verified |
| FR-14 | Offline evaluation harness (precision/recall/lat) | `eval/evaluate.py`, `tools/label_clip.py` | TC-21, TC-22 (`tests/test_eval.py`) | Verified |
| FR-15 | FP16 vs INT8 speed, power, accuracy comparison | `tools/engine_report.py`, `reports/` | TC-02, TC-23 (`tests/test_engine_report.py`) | Verified |
| FR-16 | Custom PPE detector with Edge MLOps parity | `models/` | `HUMAN_TODO.md` §4 | Pending HW |
| AC-1 | 10 minutes live run on camera without crash | `tools/soak.py`, `tests/perf/test_benchmarks.py` | TC-28 (2-min / 30-min soak test, bounded RSS delta < 15MB) | Verified |
| AC-2 | Person w/o helmet -> 1 incident in 3s; with -> 0 | `src/sentinel/domain/rules.py` | TC-12, TC-25 (`tests/test_rules.py`, `test_benchmarks.py`) | Verified |
| AC-3 | Restricted polygon -> 1 incident; re-entry -> 2 | `src/sentinel/domain/rules.py` | TC-14 (`tests/test_rules.py`) | Verified |
| AC-4 | No stored clip contains legible face | `src/sentinel/adapters/video/`, `tools/privacy_audit.py` | TC-18 (`tests/test_evidence.py`, `make test-privacy`) | Verified |
| AC-5 | >= 85% recall, 80% precision on held-out clip | `eval/evaluate.py` | TC-21, TC-22 (`tests/test_eval.py`) | Verified |
| AC-6 | INT8 faster than FP16 with quantified accuracy | `tools/engine_report.py` | TC-02, TC-23 (`tests/test_engine_report.py`) | Verified |
| AC-7 | Dashboard displays incident within 1s of MQTT | `dashboard/`, `src/sentinel/interfaces/api/` | TC-19, TC-20 (`tests/test_api_v1.py`) | Verified |
| NFR-1 | Edge Rule Engine throughput >= 25 FPS with 20 persons | `src/sentinel/domain/rules.py` | TC-26 (`tests/perf/test_benchmarks.py`, avg 0.88ms, p99 0.95ms) | Verified |
| NFR-2 | Fault injection resilience & zero incident loss | `src/sentinel/adapters/storage/` | TC-27 (`tests/test_storage.py`, broker drops, DB locked) | Verified |
| NFR-3 | Immutability of PipeGen export directory | `pipegen/export/` | TC-04, TC-05 (`tests/test_integrity.py`, SHA-256 manifest & scan) | Verified |
| NFR-4 | MQTT topic contract parity with architecture docs | `config/sentinel.yaml`, `docs/ARCHITECTURE.md` | TC-30 (`tests/test_integrity.py`) | Verified |
| SUB-1 | Complete Submission Pack & Automated Judge | `tools/judge.py`, `tools/make_submission.py` | `make judge` (all automated checks pass in < 5s) | Verified |
