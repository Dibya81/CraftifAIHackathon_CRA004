# SiteSentinel: 4-Minute Judge Demo Script & Pitch Deck Outline

> **Target Judging Window:** 4 minutes  
> **Host Environment:** CPU Laptop or Edge Device  
> **Ledger Provenance:** `evidence/ledger.yaml` (0 fabricated claims, SIMULATED / REAL labels strictly enforced)

---

## Part 1: Timed 4-Minute Judge Demo Walkthrough

### 0:00 - 0:45 | Scene 1: The Problem & PipeGen Pipeline Boundary
- **What to say:** "Workplace safety regulations require continuous compliance monitoring for PPE and hazardous zone intrusion. CCTV monitoring by humans suffers from cognitive fatigue. SiteSentinel sits on top of a PipeGen-compiled DeepStream edge perception pipeline to deliver deterministic, low-latency safety intelligence."
- **Exact Action / Click:**
  1. Open terminal on laptop:
     ```bash
     sentinel doctor --payload tests/fixtures/pipegen_sample_detections.json
     ```
  2. Show output: Format self-diagnosis confirms auto-detected canonical schema, matching classes, and normalized coordinates.
  3. Start the system:
     ```bash
     ./scripts/run_demo.sh --sim
     ```
- **Fallback Branch A (Camera / Pipeline Failure):**
  If live camera or simulated stream disconnects:
  - Run fallback replay:
    ```bash
    sentinel replay tests/fixtures/pipegen_real_capture.ndjson
    ```
  - Persistent blue banner "Replay: tests/fixtures/pipegen_real_capture.ndjson" displays in the control room dashboard.

---

### 0:45 - 1:45 | Scene 2: Real-Time Control Room & Debounced Rule Engine
- **What to say:** "Here is the SiteSentinel Control Room Dashboard. Notice the persistent 'Simulated data. Not a live camera.' banner, which prevents misrepresenting synthetic feeds as hardware video. The video stream overlays live SVG zone polygons: green safe walkway, yellow restricted press area, red danger crane drop."
- **Exact Action / Click:**
  1. Navigate browser to `http://localhost:5173` (or port 4173).
  2. Point to the top telemetry bar: shows 25 FPS, CPU host latency < 2ms, and component heartbeats.
  3. Watch a simulated worker enter the restricted zone without a hard hat.
  4. Point to the zone outline: pulses hazard-orange immediately upon intrusion.
  5. Point to the incident feed: the debounced `NO_HELMET` event appears at exactly 2.0 seconds (respecting `min_duration_s` debounce threshold).
- **Fallback Branch B (Network / Browser Lag):**
  Press `P` to enter fullscreen Present mode. Chrome collapses, maximizing video feed and active incident alerts.

---

### 1:45 - 2:45 | Scene 3: Privacy by Design & Tamper-Evident Audit Chain
- **What to say:** "Worker privacy is an uncompromising requirement. Our EvidenceWriter enforces a hard initialization barrier: if the source stream is unblurred, the system raises PrivacyViolationError and refuses to persist any frames. Let us verify an incident."
- **Exact Action / Click:**
  1. Click on the first incident in the incident feed or table (`/incidents`).
  2. Incident detail drawer slides in.
  3. Show the face-blurred thumbnail and playback clip.
  4. Click "Acknowledge" button: records officer acknowledgement and timestamp.
  5. Type note: "Safety warning issued to operator" and click "Add note".
  6. Navigate to Evidence screen (`/evidence`):
     - Show cryptographic genesis hash and SHA-256 hash chain.
     - Show the verified integrity badge (42 records verified, 0 tampering detected).
- **Fallback Branch C (CLI Verification):**
  Run in terminal to prove live chain verification:
  ```bash
  curl -s http://localhost:8000/api/v1/system/log-integrity
  ```

---

### 2:45 - 3:30 | Scene 4: Spatial Zone Authoring & Zero-Downtime Hot Reload
- **What to say:** "Job sites change daily as equipment moves. Operators cannot restart safety pipelines to adjust danger boundaries."
- **Exact Action / Click:**
  1. Click "Zones" on the sidebar navigation (`/zones`).
  2. Show interactive polygon editor with 8px grid snapping.
  3. Select "Crane Drop Area". Drag a vertex to expand the zone boundary.
  4. Click "Save zones" button.
  5. Notice instant toast confirmation: `PUT /api/zones` updates memory and persists configuration atomically with zero server downtime.
- **Fallback Branch D (Polygon Self-Intersection):**
  If a vertex crosses another edge, the editor immediately flags red: "Polygon has self-intersecting edges" and blocks save.

---

### 3:30 - 4:00 | Scene 5: Claims Ledger Proof & Hardware Roadmap
- **What to say:** "Every metric shown today is proven by committed raw logs in our claims ledger. All software stages pass automated verification in under 10 seconds. Hardware profiling on NVIDIA Jetson / DeepStream is marked PENDING until physical booth compilation."
- **Exact Action / Click:**
  1. Run the judge command:
     ```bash
     make judge
     ```
  2. Show judge output:
     - All stages PASS (Conditional).
     - 144 tests collected, 0 claims violations.
     - 2-minute soak test: bounded RSS growth.
  3. Direct judge to `JUDGE_REPORT.md` and `evidence/ledger.yaml`.

---

## Part 2: 5-Slide Pitch Deck Outline

### Slide 1: Problem & Industry Context
- **Title:** Industrial Site Safety at the Edge
- **Problem:** Heavy equipment yards, construction sites, and fabrication plants experience over 5,000 fatal workplace injuries annually. CCTV cameras are passive; human operators experience 90% vigilance degradation after 30 minutes.
- **Solution:** SiteSentinel transforms edge video streams into proactive safety sentinels with deterministic, low-latency spatial rule evaluation.

### Slide 2: PipeGen Edge Pipeline Architecture
- **Title:** Track A Pipeline Architecture (Decoupled & Zero-Copy)
- **Pipeline:** Video Input -> PipeGen DeepStream + TensorRT (Inference & Face Blur) -> MQTT Detection Bus -> SiteSentinel Rule Engine -> Dual Dispatch:
  1. Real-time Incident Bus (MQTT + WebSockets)
  2. Tamper-Evident Audit Ledger (JSONL + Fsync + Privacy-Enforced Evidence)
- **Boundary Guarantee:** `pipegen/export/` directory is an immutable boundary; SiteSentinel adapts to canonical, DeepStream array, and pipe-delimited stream formats.

### Slide 3: Privacy by Design & Cryptographic Integrity
- **Title:** Non-Negotiable Privacy and Proof of Safety
- **Privacy Barrier:** Automated face blurring with OpenCV Haar cascade validation (`make privacy-audit`). Hardware refusal on unblurred footage (`PrivacyViolationError`).
- **Cryptographic Audit Trail:** SHA-256 hash-chained JSONL records. Any disk tampering invalidates the genesis chain and triggers alert badges in the API and UI.

### Slide 4: Empirical Results & Honest Claims Ledger
- **Title:** Measured Performance & Verification Matrix
- **Rule Engine Throughput (MEASURED):** 1141.5 FPS on 20 simultaneous persons (CPU host, avg step 0.88 ms, p99 0.93 ms).
- **API Latency (MEASURED):** Mean latency < 2.0 ms on CPU host.
- **Continuous Soak (MEASURED):** 3,000 frames sustained, 0.09 MB RSS growth, 0 memory leaks, active tracks bounded <= 25.
- **Offline Evaluation (SIMULATED):** 100% precision, 100% recall on synthetic scenario (`site01.mp4`).
- **Edge Silicon Acceleration (PENDING):** INT8 entropy-calibrated TensorRT engine export targeted for physical booth check-in.

### Slide 5: Hackathon Readiness & Booth Deployment Roadmap
- **Title:** Booth Day Automation & Hand-off
- **Resumable Runner:** `scripts/booth_day.sh` executes the 10-step booth runbook with state persistence.
- **Hardware Doctor:** `sentinel doctor --hardware` audits driver, CUDA, TensorRT, and DeepStream versions.
- **Offline Deployment:** `scripts/make_offline_bundle.sh` packs all wheels, fonts, and assets for zero-internet venue survival.
- **Human Hand-off:** Only physical PipeGen compilation and hardware telemetry promotion remain.
