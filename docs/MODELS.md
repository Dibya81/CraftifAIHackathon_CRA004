# SiteSentinel: Baseline Perception Models

This document details the CPU-compatible baseline models tested for software development, test fixtures, and offline rule-engine evaluation.

> [!IMPORTANT]
> **Baseline Model Disclaimer**:
> These models run on CPU using ONNX Runtime. They serve as a **software baseline** for local development, tests, and clip evaluation in the absence of an NVIDIA Jetson GPU.
> All metrics generated using these baseline models are recorded in `evidence/ledger.yaml` under status `BASELINE` or `MEASURED (baseline)`. They **never** substitute for hardware-compiled PipeGen DeepStream + TensorRT output.
>
> In accordance with repository constraints, **model weight files are never committed to git**. Weights must be fetched via `scripts/fetch_baseline_model.sh`.

---

## 1. Documented & Tested Models

| Model Name | Task | Architecture | License | Format | Params / Size | SHA-256 Checksum |
|---|---|---|---|---|---|---|
| **YOLOv8n-COCO** | Person Detection | CSPDarknet + PAN | AGPL-3.0 / Enterprise Permissive Export | ONNX (FP32) | 3.2M params / 12.2 MB | `76d29da76f3ea8e52eefc73fb62bfa32db82e666ce8d21df34898144062a71f0` |
| **YOLOv8n-PPE** | Worker PPE (Person, Helmet, Vest, No-Helmet) | CSPDarknet + PAN | MIT / Apache-2.0 | ONNX (FP32) | 3.2M params / 12.4 MB | See `models/baseline/detector.onnx.sha256` |
| **MobileNetV2-SSD-Lite** | Person Detection | MobileNetV2 + SSDLite | Apache-2.0 | ONNX (FP32) | 4.3M params / 13.8 MB | Reference export |

---

## 2. Model Fetch Script & Verification

To download the verified baseline ONNX model:
```bash
./scripts/fetch_baseline_model.sh
```

The script performs the following validation steps:
1. Downloads the official release binary from an authenticated upstream repository.
2. Verifies the file size does not exceed the strict **25 MB** hackathon repository limit.
3. Computes the SHA-256 hash and records it into `models/baseline/detector.onnx.sha256`.
4. Tests model loading via ONNX Runtime `CPUExecutionProvider`.

---

## 3. Class Index Mapping

The baseline detector maps model class predictions to SiteSentinel canonical classes according to `config/sentinel.yaml`:

| Model Output ID / Name | Canonical Class Name | Description |
|---|---|---|
| `0`, `person` | `person` | Detected human worker on site |
| `1`, `helmet`, `hard_hat` | `helmet` | Safety hard hat on head |
| `2`, `no_helmet`, `head` | `no_helmet` | Explicit bare head without helmet |
| `3`, `vest`, `safety_vest` | `vest` | High-visibility reflective safety vest |
