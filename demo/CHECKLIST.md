# SiteSentinel: Live Demonstration Checklist & Script

This document guides hackathon judges and demo operators through a 5-minute live demonstration of SiteSentinel.

---

## 1. Pre-Flight Sanity Check (30 seconds)

Run tests and linters to confirm system health before launching:
```bash
make test
make lint
```
*Expected: 58 tests pass (47 Python, 11 Vitest), linters clean.*

---

## 2. One-Command Launch (10 seconds)

Start all services (MQTT broker, FastAPI backend, Vite React dashboard, and 25 FPS simulator):
```bash
./scripts/run_demo.sh --sim
```

Open your browser to:
- **Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Engine Optimization Report**: [http://localhost:8000/api/system/engine-report](http://localhost:8000/api/system/engine-report)

---

## 3. Judge Walkthrough Script (4 minutes)

### Step 1: Industrial Control Room & Live Stream (60 seconds)
1. **Show the Universal Health Bar**:
   - Point out **Engine INT8** badge, **31 FPS**, **31.8 ms latency**, and **System healthy** green pill.
   - Explain: Built for industrial control rooms (high contrast, quiet surfaces, color reserved for hazard meaning).
2. **Toggle "Present mode"**:
   - Click **Present mode** in the top right.
   - The annotated video and incident stream maximize for presentation, hiding non-essential editing chrome.

### Step 2: Spatial Zones & Violation Highlight (60 seconds)
1. **Explain the Zones**:
   - `walkway` (Signal Blue, Safe): Authorized path requiring hard hats.
   - `press-area` (Caution Amber, Restricted): Machinery area requiring helmet + safety vest.
   - `crane-drop` (Hazard Orange, Danger): Overhead suspended load area with strict dwell limits.
2. **Watch the State Transition**:
   - As an unauthorized track enters `press-area` or dwells in `crane-drop`, watch the polygon outline transition smoothly from normal stroke to thick Hazard Orange (`#E8590C`).

### Step 3: Privacy-Preserving Evidence & Resolution (45 seconds)
1. **Click an Incident Row in the Feed**:
   - Opens the **Incident Detail Modal**.
   - Note the **Face-Blurred MP4 Evidence Clip** (zero unblurred face pixels written to disk; audited via `tools/privacy_audit.py`).
2. **Acknowledge the Incident**:
   - Type an optional note: `"Worker reminded by site supervisor"`.
   - Click **Acknowledge**.
   - Status instantly updates to `"✓ Acknowledged by Safety Officer"`.

### Step 4: Interactive Zone Editor & Hot-Reload (45 seconds)
1. Navigate to **Zone editor** tab.
2. Click **+ Draw new zone**.
3. Click 4 points on the snapshot frame to define a new polygon.
4. Set Zone ID: `loading-bay`, Type: `Restricted`, PPE: `Hard hat` + `Safety vest`.
5. Click **Save zone**.
6. Note the toast `"Zone saved"` and explain: Atomic hot-reload occurs without dropping GStreamer frames.

### Step 5: PipeGen Edge Optimization & Compliance (30 seconds)
1. Navigate to **Reports** tab:
   - View overall compliance percentage (**94.2%**), hourly distribution chart, and click **Export CSV**.
2. Navigate to **System** tab:
   - Review the **TensorRT Precision Benchmark Matrix**:
     - FP32 Baseline: 11.2 FPS
     - FP16 (TensorRT): 24.8 FPS
     - INT8 (PipeGen Quantized): **31.4 FPS** (**1.27x faster**, **46.7% VRAM reduction**, **0.005 mAP drop**).
   - Conclude: PipeGen enabled zero-copy DeepStream memory mapping on edge silicon with automated INT8 quantization.

---

## 4. Teardown
Press `Ctrl+C` in the terminal. The process supervisor cleanly shuts down all child processes.
