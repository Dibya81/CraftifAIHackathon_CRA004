# SiteSentinel

<!-- CI badge goes here once a workflow exists -->

SiteSentinel is a construction-site safety monitoring system. It processes video feeds,
evaluates spatial zone intrusions and PPE compliance, emits tamper-evident incident records,
and displays alerts in a real-time dashboard. It is designed to consume the output of a
PipeGen-generated DeepStream + TensorRT pipeline via MQTT.

---

## Current Status

All claims below are generated from `evidence/ledger.yaml`.
Run `python tools/ledger.py summary` to see live counts.

<!-- BEGIN GENERATED: STATUS_TABLE -->
| Item | Status | Proof |
|------|--------|-------|
| Python test suite (101 tests) | MEASURED | [ledger: TC-COUNT](evidence/ledger.yaml) |
| Offline eval precision/recall/F1 | SIMULATED — simulator data only | [ledger: EVAL-PRECISION-SIM](evidence/ledger.yaml) |
| Engine FPS (FP32 / FP16 / INT8) | PENDING — no hardware run | [ledger: ENGINE-FPS-*](evidence/ledger.yaml) |
| INT8 speedup over FP16 | PENDING — no hardware run | [ledger: ENGINE-INT8-SPEEDUP](evidence/ledger.yaml) |
| VRAM footprint | PENDING — no hardware run | [ledger: ENGINE-VRAM-INT8](evidence/ledger.yaml) |
| PipeGen Stage 5 export | PENDING — pipegen/export/ is empty | [ledger: PIPEGEN-EXPORT](evidence/ledger.yaml) |
| Pipeline IR screenshot | PENDING — needs real PipeGen run | [ledger: PIPEGEN-IR-SCREENSHOT](evidence/ledger.yaml) |
| Hardware platform | PENDING — no raw log | [ledger: HARDWARE-PLATFORM](evidence/ledger.yaml) |
<!-- END GENERATED: STATUS_TABLE -->
---

## How to Run (3 commands)

```bash
# 1. Install
make install && npm --prefix dashboard install

# 2. Run simulator demo (no hardware required)
./scripts/run_demo.sh --sim
# Open http://localhost:5173

# 3. Verify
make judge
```

---

## How to Verify

```bash
python tools/ledger.py verify   # Recomputes hashes, fails on any missing source
python tools/audit_claims.py    # Scans docs for banned phrases and un-ledgered metrics
make judge                      # Runs lint + types + ledger + claims + tests
```

---

## Architecture

```
Video Source (RTSP / File) --> PipeGen DeepStream + TensorRT [PENDING]
                               |
                               | MQTT detections (sentinel/detections)
                               v
                         Python Rule Engine
                         (polygon zones, PPE state machine, debounce)
                               |
                    +----------+----------+
                    |                     |
             Incident JSONL          Evidence Writer
             (hash-chained)          (face-blurred MP4)
                    |
             FastAPI + WebSockets
                    |
             React Control Room Dashboard
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full component reference.
Architecture diagram: [docs/diagrams/architecture.png](docs/diagrams/architecture.png)

---

## PipeGen Integration

SiteSentinel is built to consume the output of a 5-stage PipeGen compilation pipeline.

| Stage | What | Status |
|-------|------|--------|
| 1 — Requirement | Frozen spec in [pipegen/requirement.md](pipegen/requirement.md) | Committed |
| 2 — Pipeline IR | DeepStream node graph (Decode→NVMM→Detector→Tracker→FaceBlur→OSD→MQTT) | Design only — PENDING real IR screenshot |
| 3 — Model Selection | Multi-class PPE detector compiled to FP16 TensorRT engine | PENDING |
| 4 — Compiler/Quantizer | INT8 entropy-calibrated engine | PENDING |
| 5 — Export Application | [pipegen/export/](pipegen/export/) | PENDING — currently empty |

The system is designed so the rule engine, incident sink, evidence writer, and dashboard
are fully independent of the PipeGen pipeline. A baseline ONNX detector (CPU) is available
for development and evaluation while the PipeGen export is pending.

To ingest a real PipeGen export:
```bash
./scripts/ingest_pipegen_export.sh <path-to-export>
```

---

## Results

> Note: All numbers are SIMULATED (simulator-generated data) or PENDING.
> No real-camera footage has been evaluated. See `evidence/ledger.yaml`.

<!-- BEGIN GENERATED: RESULTS_TABLE -->
| Metric | Value | Status | Ledger ID |
|--------|-------|--------|-----------|
| Precision | 1.0 | SIMULATED | EVAL-PRECISION-SIM |
| Recall | 1.0 | SIMULATED | EVAL-RECALL-SIM |
| F1 | 1.0 | SIMULATED | EVAL-F1-SIM |
| Mean latency | 0.125 s | SIMULATED | EVAL-LATENCY-SIM |
| FPS (INT8) | — | PENDING | ENGINE-FPS-INT8 |
| INT8 speedup | — | PENDING | ENGINE-INT8-SPEEDUP |
<!-- END GENERATED: RESULTS_TABLE -->

SIMULATED results come from `tools/simulate.py` synthetic data and cannot be interpreted
as evidence of real-world detection accuracy.

---

## Privacy

- Face blurring is enforced at the `EvidenceWriter` level: writing unblurred frames raises `PrivacyViolationError`.
- `tools/privacy_audit.py` scans all saved clips and thumbnails for unblurred faces.
- `make test-privacy` verifies zero unblurred faces in all committed media.

---

## Limitations

- No real camera footage has been recorded or evaluated. Precision/recall numbers are SIMULATED.
- No PipeGen export exists yet. The pipeline currently runs in simulator mode only.
- No GPU hardware profiling has been done. All engine FPS/latency/VRAM figures are PENDING.
- The baseline ONNX detector is CPU-only and intended for development, not production.

---

## Repo Map

```
evidence/
  ledger.yaml          # Claims ledger — single source of truth
  pipegen/             # Slot for real PipeGen exports and screenshots
  hardware/            # Slot for raw hardware logs
docs/
  ARCHITECTURE.md      # Component reference
  DATA_PROTOCOL.md     # How to record and label real footage
  RUNBOOK.md           # Booth-day checklist
  diagrams/            # Architecture diagrams
    architecture.png   # System architecture diagram
pipegen/
  export/              # Frozen PipeGen Stage 5 export (PENDING)
  requirement.md       # Stage 1 frozen spec
reports/
  engine_comparison.*  # PENDING until real speed reports exist
  simulated/           # Simulator-derived eval results (stamped SIMULATED)
src/sentinel/          # Backend: rule engine, incident sink, API, adapters
dashboard/             # React control room dashboard
tests/                 # Pytest suite (101 tests, MEASURED)
tools/
  ledger.py            # Verify and summarize claims ledger
  audit_claims.py      # Scan docs for banned phrases / un-ledgered numbers
  engine_report.py     # Generate engine comparison (refuses un-sourced numbers)
scripts/
  verify_hardware.sh   # Capture real hardware evidence
  ingest_pipegen_export.sh  # Ingest a real PipeGen export
```

---

## License

MIT. See [LICENSE](LICENSE).
