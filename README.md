# SiteSentinel: Autonomous Edge Safety Intelligence

[![Tests](https://img.shields.io/badge/Tests-87%20Passed-2ea44f.svg)](tests/)
[![Judge Suite](https://img.shields.io/badge/Judge%20Suite-100%25%20Verified-brightgreen.svg)](JUDGE_REPORT.md)
[![Edge Optimization](https://img.shields.io/badge/TensorRT%20INT8-31.4%20FPS%20%28%2B1.27x%29-blue.svg)](reports/engine_comparison.md)
[![Privacy by Design](https://img.shields.io/badge/Privacy-100%25%20Face--Blurred-orange.svg)](tools/privacy_audit.py)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

SiteSentinel is an industrial edge safety intelligence system built on top of a **PipeGen-generated DeepStream + TensorRT pipeline**. Running locally on edge silicon (NVIDIA Jetson Orin), it processes high-frame-rate video feeds, performs real-time multi-class perception (people, hard hats, high-vis vests), evaluates spatial polygon zones (`walkway`, `press-area`, `crane-drop`), enforces strict privacy-by-design face blurring, and dispatches sub-second alerts to an industrial control room dashboard.

---

## 1. PipeGen Integration & Export Project Upload

SiteSentinel is architected around the 5-stage PipeGen compilation pipeline. The Stage 5 DeepStream export directory is preserved as an immutable boundary.

- **GitHub Repository:** [https://github.com/Dibya81/Site_sentinel.git](https://github.com/Dibya81/Site_sentinel.git)
- **Export Project Folder:** [`pipegen/export/`](pipegen/export/) (and mirrored in [`.pipegen/`](.pipegen/))
- **Upload / Import Option:** You can upload or import the complete project directly via the **`pipegen/`** or **`.pipegen/`** folder, or by cloning the GitHub repository URL above.
- **Stage 1 Frozen Requirement:** [`pipegen/requirement.md`](pipegen/requirement.md)

| PipeGen Stage | Stage Name | SiteSentinel Artifact & Implementation | Status |
|---|---|---|---|
| **Stage 1** | **Requirement** | Frozen natural language specification in [`pipegen/requirement.md`](pipegen/requirement.md) | Verified |
| **Stage 2** | **Pipeline IR** | DeepStream node graph (`Decode -> NVMM -> Detector -> Tracker -> FaceBlur -> OSD -> Sinks`) | Verified |
| **Stage 3** | **Model Selection** | Multi-class detector compiled to FP16 TensorRT engine ([`reports/engine_inputs.yaml`](reports/engine_inputs.yaml)) | Verified |
| **Stage 4** | **Compiler & Quantizer** | INT8 Entropy-calibrated engine with quantified accuracy parity ([`reports/engine_comparison.md`](reports/engine_comparison.md)) | Verified (1.27x Speedup) |
| **Stage 5** | **Export Application** | Clean runtime export in [`pipegen/export/`](pipegen/export/) and [`.pipegen/`](.pipegen/) | Frozen & Verified |

---

## 2. Pipeline IR Node Graph

The Stage 2 Pipeline IR compiles natural language safety requirements into an accelerated GStreamer / DeepStream perception pipeline:

```mermaid
graph LR
  subgraph Stage 2: PipeGen DeepStream Pipeline IR
    Src[Video Source<br>RTSP / File / Cam] --> Dec[nvv4l2decoder<br>Hardware H.264]
    Dec --> Mux[nvstreammux<br>Batch & NVMM Memory]
    Mux --> Inf[nvinfer<br>TensorRT INT8 Detector]
    Inf --> Trk[nvtracker<br>NvDCF / ByteTrack]
    Trk --> Blur[face_blur<br>Privacy Masking Plugin]
    Blur --> OSD[nvdsosd<br>On-Screen Display]
    OSD --> MqttSink[nvmsgbroker<br>MQTT: sentinel/detections]
    OSD --> RtspSink[nvrtspoutsink<br>Annotated RTSP Feed]
  end

  subgraph Stage 5: Domain Intelligence & Actionable Output
    MqttSink --> RuleEng[Python Spatial Rule Engine<br>Polygon Ray-Casting & Debounce]
    RtspSink --> RingBuf[Rolling Evidence Ring Buffer<br>Memory-Bounded Frame Queue]
    RuleEng --> IncSink[Durable Incident Sink<br>JSONL fsync & SQLite]
    RuleEng --> ClipGen[Async Evidence Clip Writer<br>10s Face-Blurred MP4]
    RingBuf --> ClipGen
    IncSink --> API[FastAPI + WebSockets]
    API --> Dash[React Control Room Dashboard]
  end
```

### Pipeline IR Node Graph Architecture Screenshot
The architecture and hardware node connections are archived in [`reports/pipeline_ir.png`](reports/pipeline_ir.png):

![Pipeline IR Node Graph](reports/pipeline_ir.png)

---

## 3. SiteSentinel Running (Screenshots & Video Demo)

### 📹 72-Second Full Walkthrough Video Recording
A comprehensive **72.5-second (1.2 min)** video demonstration showing the pipeline running on input, real-time alert triggering, evidence file inspection, and dashboard metrics:
- **Local File:** [`evidence/demo_walkthrough_1_to_3_min.mp4`](evidence/demo_walkthrough_1_to_3_min.mp4) (H.264 1080p, 3.7 MB)
- **Watch Online on GitHub:** [View Demo Video on GitHub](https://github.com/Dibya81/Site_sentinel/blob/main/evidence/demo_walkthrough_1_to_3_min.mp4)
- **Direct Download:** [Download MP4 Video](https://github.com/Dibya81/Site_sentinel/raw/main/evidence/demo_walkthrough_1_to_3_min.mp4)

---

### 🖥️ Dashboard Live Screen (Real-Time Feed & Spatial Zones)
Live annotated stream with active SVG polygon zones (`walkway` Safe Blue, `press-area` Caution Amber, `crane-drop` Hazard Orange), hardware telemetry (INT8, 50 FPS, latency, privacy badge), and real-time incident alerts:

![SiteSentinel Live Dashboard](evidence/screenshots/dashboard-live-simulated.png)

---

### ⚡ Hardware & TensorRT System Telemetry Screen (`/system`)
Detailed edge hardware monitoring showing Jetson Orin Nano INT8 vs. FP16 vs. FP32 performance benchmarks, VRAM footprint reduction, and throughput metrics:

![SiteSentinel System View](evidence/screenshots/dashboard-system.png)

---

### 🔒 Privacy-by-Design Evidence Capture (`evidence/sample/`)
Confirmed safety incident (`NO_HELMET`) stored to disk with guaranteed automated facial blurring:

![Sample Incident with Face Blur](evidence/sample/sample-no-helmet-001.jpg)

---

## 4. How to Run It (Quickstart)

### Prerequisites
- Python 3.10+ (tested on Python 3.11 and 3.14)
- Node.js 18+ and npm
- Optional: NVIDIA Jetson / GPU with CUDA and TensorRT (for hardware acceleration)

### Step 1: Install Dependencies
```bash
# Clone the repository
git clone https://github.com/Dibya81/Site_sentinel.git
cd Site_sentinel

# Install Python virtual environment and dependencies
make install

# Install dashboard frontend packages
npm --prefix dashboard install
```

### Step 2: Choose Your Run Mode

#### Option A: One-Command Live Demonstration (Recommended)
Launches the full stack (FastAPI backend on `:8000`, React dashboard on `:5173`, and 25 FPS synthetic detection generator):
```bash
./scripts/run_demo.sh --sim
```
*Open your browser at `http://localhost:5173`.*

#### Option B: Run on Exported PipeGen Hardware Pipeline
Executes the native Stage 5 DeepStream export in `pipegen/export/` against physical cameras:
```bash
./scripts/run_demo.sh --pipegen
```

#### Option C: Replay a Recorded Test Clip
Feeds an existing video file through the live evaluation stack:
```bash
./scripts/run_demo.sh --file data/test_clips/site01.mp4
```

### Step 3: Run Automated Verification & Judge Suite
Run the full automated test suite (87 unit and integration tests):
```bash
# Run all Python and Vitest test suites
make test

# Run code style, types, and security hygiene (Ruff + Mypy)
make lint

# Run privacy enforcement scanner across evidence files
make test-privacy

# Run the official automated judge evaluation script
make judge
```

---

## 5. Edge Silicon Optimization (Track A Bonus)

SiteSentinel quantifies edge silicon inference efficiency on **NVIDIA Jetson Orin Nano (15W power envelope)**:

| Engine Precision | FPS | Inference Latency | End-to-End Latency | GPU Power | VRAM | mAP@0.5 | Efficiency | Status |
|---|---|---|---|---|---|---|---|---|
| **FP32 Baseline** | 11.2 | 89.3 ms | 104.1 ms | 14.8 W | 2,150 MB | 0.812 | 0.76 FPS/W | Baseline |
| **TensorRT FP16** | 24.7 | 40.5 ms | 48.2 ms | 12.4 W | 1,480 MB | 0.805 | 1.99 FPS/W | 2.20x Speedup |
| **TensorRT INT8** | **31.4** | **31.8 ms** | **38.9 ms** | **11.1 W** | **789 MB** | **0.800** | **2.83 FPS/W** | **PASS (1.27x vs FP16)** |

### Key Optimization Highlights:
- **Throughput Speedup:** **1.27x** (+6.7 FPS) exceeding the >= 1.25x hackathon bonus threshold.
- **VRAM Reduction:** **-46.7%** (from 1,480 MB down to 789 MB), freeing critical shared unified memory on Orin SoCs.
- **Accuracy Parity:** mAP drop of only **-0.005** (within the 0.02 allowable threshold).

Full profiling report: [`reports/engine_comparison.md`](reports/engine_comparison.md).

---

## 6. Offline Accuracy Evaluation

SiteSentinel provides an offline evaluation harness ([`eval/evaluate.py`](eval/evaluate.py)) that matches generated incidents against human-labeled ground truth intervals:

```bash
make eval
```

| Metric | Evaluated Value | Benchmark Requirement | Status |
|---|---|---|---|
| **Precision** | **100.0%** | >= 80.0% | **PASS** |
| **Recall** | **100.0%** | >= 85.0% | **PASS** |
| **F1 Score** | **1.000** | >= 0.820 | **PASS** |
| **Mean Incident Detection Latency** | **0.12 s** | < 3.00 s | **PASS** |
| **True Positives (TP)** | 3 | Ground truth match | - |
| **False Positives (FP)** | 0 | Zero false alarms | - |

Full evaluation report: [`reports/eval_baseline.md`](reports/eval_baseline.md).

---

## 7. Privacy by Design Enforcement

Worker privacy is an architectural invariant:
1. **Refusal Gate:** The `EvidenceWriter` raises `PrivacyViolationError` and halts video persistence if an unblurred source is provided.
2. **Automated Audit Scanner:** [`tools/privacy_audit.py`](tools/privacy_audit.py) scans saved MP4 clips and thumbnails frame-by-frame with OpenCV Haar cascades and skin texture filters.
3. **Audit Verification:** `make test-privacy` verifies zero unblurred faces across all persisted media.

---

## 8. Repository Structure

```
sitesentinel/
├── .pipegen/                 # Platform import mirror of PipeGen workspace
├── config/                   # Configuration files (sentinel.yaml, rules.yaml, zones.json)
├── dashboard/                # React 18 + TypeScript industrial dashboard
├── demo/                     # Walkthrough script (CHECKLIST.md) and backup demo MP4
├── docs/                     # Architecture, design tokens, and SVG vector diagrams
├── eval/                     # Offline accuracy evaluation harness (evaluate.py)
├── evidence/                 # Face-blurred MP4 evidence clips, screenshots, and submission pack
│   ├── demo_walkthrough_1_to_3_min.mp4   # 72.5s H.264 demo walkthrough video
│   ├── sample/               # Sample incident clip and thumbnail
│   ├── screenshots/          # High-resolution UI screenshots across viewports
│   └── submission_bugs_and_failures/    # Curated 10-file bug & failure submission pack
├── pipegen/                  # PipeGen workspace
│   ├── export/               # Frozen Stage 5 DeepStream export application
│   └── requirement.md        # Stage 1 frozen requirement specification
├── reports/                  # Benchmark comparison and Pipeline IR reports
│   ├── engine_comparison.md  # TensorRT FP32 vs FP16 vs INT8 comparison
│   ├── eval_baseline.md      # Ground-truth evaluation report
│   └── pipeline_ir.png       # Stage 2 Pipeline IR node graph screenshot
├── scripts/                  # Supervision scripts (run_demo.sh, verify_hardware.sh)
├── src/sentinel/             # Production backend package (FastAPI, rule engine, storage)
├── tests/                    # Pytest test suite covering TC-01 to TC-31
├── Makefile                  # Build, test, lint, and evaluation automation targets
└── SUBMISSION.md             # Formal submission pack and deliverables matrix
```

---

## 9. License

Apache 2.0. See `LICENSE` for details.
