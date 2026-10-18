# SiteSentinel: Booth Day Hardware & PipeGen Runbook

This runbook defines the exact numbered checklist with checkboxes for human team members during onsite booth evaluation (Track A: PipeGen). Complete every step in sequence to transform all `PENDING` items in `evidence/ledger.yaml` into verified `MEASURED` claims.

---

## Booth Checklist Summary

- [ ] Step 1: Host Environment & Tooling Verification
- [ ] Step 2: Install PipeGen & Record Version
- [ ] Step 3: Run PipeGen Pipeline Stages & Compile TensorRT Engine
- [ ] Step 4: Capture Real Pipeline IR Node Graph Screenshot
- [ ] Step 5: Ingest PipeGen Export Deliverables
- [ ] Step 6: Execute Live Hardware Verification & Telemetry Sampling
- [ ] Step 7: Record Physical Evaluation Clips & Generate Labels
- [ ] Step 8: Run Offline Perception Evaluation on Physical Footage
- [ ] Step 9: Re-generate Engine Comparison & Failure Analysis Reports
- [ ] Step 10: Update Claims Ledger & Run Final Audit Gate

---

## Detailed Step-by-Step Instructions

### Step 1: Host Environment & Tooling Verification
- [ ] **Action**: Open terminal on target Linux host and confirm hardware accelerators:
  ```bash
  nvidia-smi || tegrastats
  ```
- [ ] **Expected Output**: Active GPU device displayed with driver version and CUDA capability.
- [ ] **Action**: Run SiteSentinel diagnostic doctor:
  ```bash
  sentinel doctor
  ```
- [ ] **Expected Output**: Core dependencies report `[PASS]`.

---

### Step 2: Install PipeGen & Record Version
- [ ] **Action**: Ensure the PipeGen compiler CLI is installed and in `$PATH`:
  ```bash
  pipegen --version
  ```
- [ ] **Expected Output**: Clean version string (e.g., `pipegen 0.5.1` or newer).
- [ ] **Action**: Record the version string:
  ```bash
  pipegen --version > evidence/pipegen/version.txt
  ```

---

### Step 3: Run PipeGen Pipeline Stages & Compile TensorRT Engine
- [ ] **Action**: Run the PipeGen multi-stage build pipeline:
  ```bash
  pipegen build \
    --config config/pipegen_pipeline.yaml \
    --target trt \
    --precision int8 \
    --calib-data data/calibration \
    --output build/pipegen_export
  ```
- [ ] **Expected Output**: PipeGen executes stages 1 through 5, generating:
  - `pipegen_ppe_int8.engine` (TensorRT INT8 engine)
  - `pipegen_ppe_fp16.engine` (TensorRT FP16 engine)
  - `pipeline_ir.json` (intermediate representation graph)
  - `speed_report.json` (benchmark throughput and latency)
- [ ] **Action**: Copy compiled engine files to `models/engines/`:
  ```bash
  mkdir -p models/engines
  cp build/pipegen_export/*.engine models/engines/
  ```

---

### Step 4: Capture Real Pipeline IR Node Graph Screenshot
- [ ] **Action**: Open PipeGen visualization tool or web UI inspecting `build/pipegen_export/pipeline_ir.json`:
  ```bash
  pipegen view build/pipegen_export/pipeline_ir.json
  ```
- [ ] **Action**: Capture full screenshot of the node graph (showing preprocessing, backbone, detection heads, and post-processing nodes).
- [ ] **Action**: Save the screenshot directly to:
  ```bash
  cp /path/to/screenshot.png evidence/pipegen/pipeline_ir.png
  ```
- [ ] **Action**: Remove the pending notice file:
  ```bash
  rm -f evidence/pipegen/pipeline_ir.png.README
  ```

---

### Step 5: Ingest PipeGen Export Deliverables
- [ ] **Action**: Run the automated export ingestion script:
  ```bash
  ./scripts/ingest_pipegen_export.sh build/pipegen_export
  ```
- [ ] **Expected Output**:
  - Artifacts copied into `pipegen/export/`
  - `pipegen/export/.manifest.sha256` generated
  - Root `pipegen/export.sha256` written
  - Adapter parsing verified against detection sample

---

### Step 6: Execute Live Hardware Verification & Telemetry Sampling
- [ ] **Action**: Run the hardware verification harness for at least 2 minutes on target hardware:
  ```bash
  ./scripts/verify_hardware.sh 2
  ```
- [ ] **Expected Output**:
  - Raw system log written to `evidence/hardware/run_<timestamp>.log`
  - Telemetry log written to `evidence/hardware/telemetry_<timestamp>.log`
  - Automated performance summary JSON written to `evidence/hardware/summary_<timestamp>.json`
  - Detections per second and MQTT arrival latencies logged

---

### Step 7: Record Physical Evaluation Clips & Generate Labels
- [ ] **Action**: Record at least 30 physical violation events on the live test site across lighting conditions (per `docs/DATA_PROTOCOL.md`).
- [ ] **Action**: Place video files in `data/test_clips/`:
  ```bash
  cp /path/to/recorded_clip.mp4 data/test_clips/site01_test.mp4
  ```
- [ ] **Action**: Label ground truth using `tools/label_clip.py`:
  ```bash
  python tools/label_clip.py \
    --clip data/test_clips/site01_test.mp4 \
    --out data/labelled/site01_test.json \
    --add "NO_HELMET:2.0:7.0:1:press-area" \
    --add "ZONE_INTRUSION:10.0:15.0:2:crane-drop"
  ```

---

### Step 8: Run Offline Perception Evaluation on Physical Footage
- [ ] **Action**: Execute offline evaluation with real detector outputs:
  ```bash
  python eval/evaluate.py \
    --clip data/test_clips/site01_test.mp4 \
    --labels data/labelled/site01_test.json \
    --provenance MEASURED \
    --out-dir reports
  ```
- [ ] **Expected Output**:
  - `reports/eval_<timestamp>.md` and `.json` generated
  - Per-rule precision, recall, F1, and Wilson 95% confidence intervals
  - AC-5 PASS status confirmed if Precision >= 0.80 and Recall >= 0.85 across >= 30 events

---

### Step 9: Re-generate Engine Comparison & Failure Analysis Reports
- [ ] **Action**: Populate `reports/engine_inputs.yaml` with the exact paths and SHA-256 hashes of the raw speed reports in `evidence/pipegen/`.
- [ ] **Action**: Run the comparison report generator:
  ```bash
  python tools/engine_report.py --inputs reports/engine_inputs.yaml --out-dir reports
  ```
- [ ] **Expected Output**:
  - `reports/engine_comparison.md` and `.json` generated with non-null numbers
  - Each metric linked to its raw source file and SHA-256

---

### Step 10: Update Claims Ledger & Run Final Audit Gate
- [ ] **Action**: Update `evidence/ledger.yaml` with measured values and source file paths/hashes for:
  - `pipegen_export`
  - `pipegen_pipeline_ir`
  - `hardware_run`
  - `engine_comparison`
  - `perception_eval`
- [ ] **Action**: Re-render documentation from the ledger:
  ```bash
  python tools/render_docs.py
  ```
- [ ] **Action**: Verify ledger integrity:
  ```bash
  python tools/ledger.py verify
  ```
- [ ] **Action**: Run claims audit tool:
  ```bash
  python tools/audit_claims.py
  ```
- [ ] **Action**: Run the complete judge gate:
  ```bash
  make judge
  ```
- [ ] **Expected Output**: 0 violations, all documentation clean, unconditional PASS.
