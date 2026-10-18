# SiteSentinel: Bugs and Failures Submission Pack

This directory contains **10 curated files** (Screenshots and Videos, all under 5 MB, well below the 100 MB limit) prepared for submission under:
`Attach Screenshots/Videos of the Bugs/Failures`

---

## File Inventory & Explanations

### 1. `01_bug_system_page_crash.png` (Screenshot - 62 KB)
- **Category:** Software Bug / Client-Side Crash
- **Location:** Dashboard `/system` route (`dashboard/src/components/SystemView.tsx`)
- **Bug Description:** Uncaught `TypeError: engineReport.models.map is not a function`. The backend benchmark report API returned an object mapping model names to metrics (`{"fp32": ..., "fp16": ..., "int8": ...}`), while the frontend expected an array and called `.map()`, resulting in a client crash.

---

### 2. `02_bug_system_page_error_state.png` (Screenshot - 43 KB)
- **Category:** Error State & Resilience Handling
- **Location:** System View Error Boundary
- **Bug Description:** Demonstrates the system page error handling and retry prompt when API connections fail or invalid payloads are returned.

---

### 3. `03_bug_dashboard_initial_broken_feed.png` (Screenshot - 272 KB)
- **Category:** Visual & Telemetry Authenticity Bug
- **Location:** Dashboard Live Screen (`localhost:4173`)
- **Bug Description:** Broken camera panel showing a black canvas with a broken image placeholder and floating SVG zones over empty space. The telemetry bar simultaneously displayed fake mock metrics ("System operational", "Engine INT8", "25 FPS", "38.9 ms", "GPU 38%") without any active hardware running.

---

### 4. `04_safety_failure_no_helmet_detected.jpg` (Screenshot - 25 KB)
- **Category:** Physical AI Safety Failure (Violation Incident)
- **Location:** Spatial PPE Rule Engine (`src/sentinel/domain/rules.py`)
- **Bug/Failure Description:** Safety compliance failure event where a worker was detected inside a restricted hazardous zone without a required safety helmet (`NO_HELMET`). Privacy-by-design face-blur is actively preserved.

---

### 5. `05_safety_failure_evidence_clip.mp4` (Video - 121 KB)
- **Category:** Safety Incident Evidence Video
- **Location:** Evidence Ring Buffer (`src/sentinel/adapters/video/clip_writer.py`)
- **Bug/Failure Description:** 10-second standardized MP4 evidence video recording the safety rule failure with guaranteed privacy masking (100% blurred faces).

---

### 6. `06_video_system_page_bug_reproduce_and_fix.webp` (Video - 1.2 MB)
- **Category:** Bug Reproduction & Fix Verification Video
- **Location:** Dashboard `/system` route
- **Bug Description:** Browser recording reproducing the `/system` crash and verifying the live fix with normalized dictionary-to-array transformation.

---

### 7. `07_video_initial_dashboard_audit.webp` (Video - 3.5 MB)
- **Category:** Full UI Failure Audit Video
- **Location:** Complete Dashboard Walkthrough
- **Bug Description:** Video recording documenting initial UI bugs across navigation, feed interactions, unverified face-blur badges, and missing simulated stream disclosures.

---

### 8. `08_video_redesigned_dashboard_audit.webp` (Video - 2.5 MB)
- **Category:** Multi-Resolution & Responsive Layout Audit
- **Location:** Dashboard Stress Test
- **Bug Description:** Responsive audit recording demonstrating stress testing and fixing layout bugs across desktop (1440px), tablet (1024px), and mobile (390px) viewports.

---

### 9. `09_fixed_system_view_verification.png` (Screenshot - 307 KB)
- **Category:** Before / After Verification
- **Location:** System View (`/system`)
- **Fix Description:** Resolved `/system` view properly displaying the full Jetson Orin TensorRT FP32 / FP16 / INT8 benchmark table with FPS, latency, VRAM, and power efficiency.

---

### 10. `10_fixed_live_view_verification.png` (Screenshot - 311 KB)
- **Category:** Before / After Verification
- **Location:** Live Camera Screen
- **Fix Description:** Resolved live dashboard showing active MJPEG camera stream, persistent "Simulated data. Not a live camera." banner, spatial polygons, and real-time incident feed.
