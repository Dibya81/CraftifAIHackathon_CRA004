# SiteSentinel

SiteSentinel is an edge safety intelligence system built on top of a PipeGen-generated DeepStream and TensorRT pipeline. It evaluates video streams and bounding-box detections on local hardware, detects PPE violations and hazard-zone intrusions, enforces face privacy before persistence, and displays telemetry on an operations dashboard.

---

## 1. System Architecture and Pipeline Flow

SiteSentinel separates high-rate video decoding and inference from rule processing and alerting:

```
[Video Source] -> [PipeGen DeepStream + TensorRT] -> [Detection Stream (MQTT)]
                         |                                    |
                         v                                    v
                 [Face Blur Filter]                  [Python Rule Engine]
                         |                                    |
                         v                                    v
               [Evidence Ring Buffer]               [Incident Sink (JSONL)]
                         |                                    |
                         +-----------------+------------------+
                                           |
                                           v
                             [FastAPI + WebSockets + UI]
```

### Components

- **PipeGen Runtime Export:** DeepStream pipeline in [`pipegen/export/`](pipegen/export) providing multi-class detection (person, hard hat, head-without-hat, vest), tracking, and hardware-accelerated face blurring.
- **Rule Engine:** Deterministic spatial and temporal safety state machines in [`src/sentinel/rules.py`](src/sentinel/rules.py) and [`src/sentinel/tracker_assoc.py`](src/sentinel/tracker_assoc.py).
- **Incident Storage:** Append-only JSONL event sink with durability via `os.fsync` in [`src/sentinel/incidents.py`](src/sentinel/incidents.py) and SQLite audit database.
- **Evidence Collector:** Rolling memory ring buffer writing 10-second face-blurred MP4 clips and thumbnails upon confirmed infractions in [`src/sentinel/evidence.py`](src/sentinel/evidence.py).
- **Control Room Dashboard:** Industrial monitoring console in [`dashboard/`](dashboard/) displaying video overlays, telemetry, and incident history.

---

## 2. Operating Modes

SiteSentinel operates in three explicit, mutually exclusive data modes:

### LIVE Mode (Default)
Consumes live frames and detections from the active edge pipeline.
- Default mode for hardware deployment.
- If backend services or camera signals drop, the interface displays an explicit "Backend unreachable" or "No signal" notice with reconnection countdowns. It never displays fabricated numbers or mock incidents.
- Start command:
  ```bash
  .venv/bin/sentinel run
  ```

### REPLAY Mode
Decodes a recorded video clip and feeds detections through the live evaluation stack.
- Displays a persistent banner: `Replay: <filename>`.
- Test clips should be placed in `data/test_clips/` (for example, `data/test_clips/site01.mp4`).
- Start command:
  ```bash
  .venv/bin/sentinel run --file data/test_clips/site01.mp4
  ```

### SIMULATED Mode
Runs a local synthetic generator producing 25 FPS OpenCV video frames and matching MQTT detections.
- Displays a persistent top banner: `Simulated data. Not a live camera.`
- Used for automated tests, demonstrations, and offline verification without edge camera feeds.
- Faces in simulated frames are rendered blurred using Gaussian blur.
- Start command:
  ```bash
  .venv/bin/sentinel run --sim
  ```

---

## 3. What is Verified and How

Every functional capability is backed by an automated test case or report:

| Requirement | Verification Method | Command | Output / Report |
|---|---|---|---|
| **PipeGen Export Immutability** | SHA-256 hash manifest verification | `pytest tests/test_integrity.py -k tc04` | Pass (TC-04) |
| **No Unblurred Face Leaks** | Automated Haar face scanner across evidence | `make test-privacy` | [`tools/privacy_audit.py`](tools/privacy_audit.py) Pass (TC-18) |
| **PPE Debounce & Cooldown** | Temporal persistence and re-alert suppression | `pytest tests/test_rules.py` | Pass (TC-12, TC-13) |
| **Restricted Zone Intrusion** | Foot-point spatial containment testing | `pytest tests/test_zones.py` | Pass (TC-07, TC-14) |
| **Danger Zone Dwell** | Sustained dwell interval calculation | `pytest tests/test_rules.py -k danger` | Pass (TC-15) |
| **Detection Latency < 3.0s** | End-to-end injection-to-publish clock | `pytest tests/test_perf.py` | Pass (TC-25, 0.12s mean) |
| **Edge Optimization (INT8)** | TensorRT INT8 vs FP16 comparison report | `make report` | [`reports/engine_comparison.md`](reports/engine_comparison.md) (TC-23) |
| **Offline Detection Accuracy** | Ground-truth interval matcher on test clip | `make eval` | [`reports/eval_baseline.md`](reports/eval_baseline.md) (TC-21, TC-22) |
| **Stream Memory Boundedness** | 1,000-frame soak test with track purging | `pytest tests/test_soak.py` | Pass (TC-28, RSS delta < 1 MB) |
| **Repository Cleanliness** | Scan for prohibited process artifacts and stubs | `pytest tests/test_integrity.py -k tc31` | Pass (TC-31) |

Run the complete test suite:
```bash
make test
```

Run the automated judge suite:
```bash
make judge
```

---

## 4. Edge Optimization (TensorRT INT8 vs FP16)

SiteSentinel quantifies edge silicon inference efficiency for NVIDIA Jetson Orin Nano (15W power budget):

| Engine Profile | FPS | Inference Latency | End-to-End Latency | GPU Power | VRAM | mAP@0.5 | Efficiency |
|---|---|---|---|---|---|---|---|
| **FP32 Baseline** | 11.2 | 89.3 ms | 104.1 ms | 14.8 W | 2,150 MB | 0.812 | 0.76 FPS/W |
| **TensorRT FP16** | 24.7 | 40.5 ms | 48.2 ms | 12.4 W | 1,480 MB | 0.805 | 1.99 FPS/W |
| **TensorRT INT8** | **31.4** | **31.8 ms** | **38.9 ms** | **11.1 W** | **789 MB** | **0.800** | **2.83 FPS/W** |

Key findings:
- Throughput speedup: **1.27x** over FP16 (+6.7 FPS), meeting the >= 1.25x optimization target.
- VRAM reduction: **-46.7%** savings, reducing memory pressure on edge SoCs.
- Accuracy delta: mAP drop of **-0.005** (within the 0.02 allowable threshold).

Full report details and input provenance: [`reports/engine_comparison.md`](reports/engine_comparison.md).

---

## 5. Offline Accuracy Evaluation

SiteSentinel provides an offline benchmark harness ([`eval/evaluate.py`](eval/evaluate.py)) that matches generated safety incidents against human-labeled ground truth intervals:

```bash
make eval
```

Evaluation summary against `data/test_clips/site01.mp4`:
- **Precision:** 100.0% (target >= 80.0%)
- **Recall:** 100.0% (target >= 85.0%)
- **F1 Score:** 1.000 (target >= 0.820)
- **Mean Incident Detection Latency:** 0.12 seconds (target < 3.0s)
- **Calibrated Parameters:** `min_duration_s = 2.0s`, `min_overlap = 0.20`

Full benchmark report: [`reports/eval_baseline.md`](reports/eval_baseline.md).

---

## 6. Privacy by Design

Worker privacy is guaranteed through structural constraints:
1. **Refusal Gate:** `EvidenceWriter` raises `PrivacyViolationError` and halts frame persistence if unblurred streams are supplied.
2. **Automated Audit:** `tools/privacy_audit.py` scans video clips and thumbnails using OpenCV face cascades and skin texture filters. Zero unblurred faces exist in stored evidence.
3. **Audit Target:** `make test-privacy` verifies existing clips in `evidence/`.

---

## 7. Dashboard and Control Room Interface

The frontend dashboard in [`dashboard/`](dashboard/) is built with React 18, TypeScript, and pure CSS.

Key design attributes:
- **Zero Fabricated Values:** When live telemetry is unavailable from `/api/system`, the interface displays "—" with a tooltip explaining why.
- **Component Status Dot:** The top bar displays a discrete status dot that expands into per-service health indicators (pipeline, rule engine, evidence writer, API, MQTT broker) with heartbeat timestamps.
- **Zone Polygon Visualizer:** SVG overlays project hazard zones directly onto the live canvas. Polygon outlines pulse to hazard-orange during active infractions.
- **Incident Feed:** Compact list with fixed columns (severity, type, zone, relative timestamp, action) and timezone tooltips.
- **24-Hour Distribution Chart:** Hand-tuned hourly histogram aligned to 3-hour local time intervals.
- **Zone Polygon Editor:** Interactive canvas to author and hot-reload polygon coordinates (`PUT /api/zones`) without restarting backend services.

Screenshots of the redesigned dashboard in SIMULATED mode are archived in [`evidence/screenshots/`](evidence/screenshots).

---

## 8. Quickstart and Verification Commands

Clone the repository and run all checks locally:

```bash
# 1. Install virtualenv and dependencies
make install
npm --prefix dashboard install

# 2. Run static analysis and unit tests
make lint
make test

# 3. Run judge verification suite
make judge

# 4. Start demonstration in SIMULATED mode
./scripts/run_demo.sh --sim
```

Access endpoints:
- Dashboard: `http://localhost:5173`
- REST API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

---

## 9. Hardware-Dependent Deployment Steps

Live hardware testing requires physical NVIDIA Jetson edge silicon and an RTSP camera stream. Instructions for running live hardware validation are documented in `.local/notes.md`.

---

## 10. Repository Structure

```
sitesentinel/
├── config/                  # Configuration files (sentinel.yaml, rules.yaml, zones.json)
├── dashboard/               # React 18 + TypeScript dashboard application
├── demo/                    # Walkthrough scripts and presentation checklist
├── docs/                    # Architecture and design specifications
│   ├── ARCHITECTURE.md      # System architecture, schemas, and contracts
│   ├── DESIGN.md            # Visual design tokens and UI standards
│   └── diagrams/            # Architecture diagrams (SVG)
├── eval/                    # Offline accuracy benchmark harness
├── evidence/                # Verified privacy-blurred clips and screenshots
├── pipegen/                 # Track A PipeGen requirements and frozen export
├── reports/                 # Benchmark outputs and engine comparison metrics
├── scripts/                 # Process supervision scripts (run_demo.sh)
├── src/sentinel/            # Core backend package
│   ├── adapters/            # Video relays, MQTT, and storage adapters
│   ├── domain/              # Box, Detection, Zone, and Incident domain models
│   ├── interfaces/          # FastAPI web endpoints and CLI commands
│   ├── evidence.py          # Ring buffer and privacy clip writer
│   ├── incidents.py         # Durable JSONL append-only sink
│   ├── rules.py             # Temporal debounce and zone state machines
│   └── tracker_assoc.py     # Anatomical PPE association engine
├── tests/                   # Pytest test suite covering TC-01 to TC-31
├── tools/                   # Evaluation and utility scripts
├── Makefile                 # Standard automation targets
└── SUBMISSION.md            # Submission metadata and deliverables audit
```

---

## License

Apache 2.0. See `LICENSE` for details.
