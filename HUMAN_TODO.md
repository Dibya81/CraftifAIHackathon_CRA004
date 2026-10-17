# SiteSentinel: Human & Hardware Tasks (HUMAN_TODO.md)

This file tracks all physical hardware, GPU, PipeGen CLI/GUI, and manual tasks required for full deployment. The software stack runs offline and headless against fixtures and simulators; real hardware data is plugged in via the steps below.

---

## 1. PipeGen Pipeline Generation (Stage 1 to 5)
- [ ] **Install PipeGen v0.5.1**:
  - Verify installation: `pipegen --version` (must output `0.5.1`).
- [ ] **Stage 1 (Requirement)**:
  - Copy requirement from `pipegen/requirement.md`.
  - Enter into PipeGen GUI/CLI.
- [ ] **Stage 2 (Pipeline IR)**:
  - Inspect the generated DeepStream pipeline graph.
  - Save node graph screenshot to `reports/pipeline_ir.png`.
- [ ] **Stage 3 & 4 (Model & Compiler)**:
  - Build FP16 TensorRT engine: export speed report to `reports/speed_report_fp16.txt` (or `.json`).
  - Build INT8 TensorRT engine: export speed report to `reports/speed_report_int8.txt` (or `.json`).
- [ ] **Stage 5 (Export)**:
  - Export generated DeepStream application into `pipegen/export/`.
  - **CRITICAL**: Do NOT edit files inside `pipegen/export/` manually.

## 2. PipeGen Real Sample Output Capture
- [ ] **Capture MQTT / JSON sample**:
  - Run the exported pipeline against a sample video: `cd pipegen/export && ./run.sh --input ../../data/test_clips/site01.mp4`.
  - Capture 100 frames of output from MQTT topic `sentinel/detections` or the file sink.
  - Save sample payload to `tests/fixtures/pipegen_sample.json`.
  - Run verification test: `pytest tests/test_pipegen_adapter.py`.

## 3. Physical Camera & Live Run (Acceptance Criteria AC-1)
- [ ] **Connect USB / RTSP Camera**:
  - Identify video device: `v4l2-ctl --list-devices` (e.g. `/dev/video0`).
  - Update `camera_id` and video input in `config/sentinel.yaml` if needed.
- [ ] **10-minute Live Stability Run**:
  - Run `./scripts/run_demo.sh`.
  - Walk in front of camera with hard hat (compliant).
  - Remove hard hat for >2 seconds (verify single NO_HELMET alert within 3s).
  - Walk into restricted zone (verify ZONE_INTRUSION alert).
  - Verify zero crashes over 10 continuous minutes.

## 4. INT8 Calibration Dataset
- [ ] **Capture 500+ calibration frames**:
  - Record varied lighting, distances, and angles from the site.
  - Store frames in `models/calibration/`.
  - Pass directory to PipeGen INT8 quantizer.
