# SiteSentinel: Automated Judge Verification Report

- **Execution Date**: `2026-10-18 21:30:12 UTC`
- **Host Platform**: `Darwin arm64`
- **Python Version**: `3.11.15`
- **Total Judge Duration**: `6.58 seconds` (Target < 180 s)
- **Overall Evaluation Status**: **CONDITIONAL PASS (Hardware evidence pending)**

## Judge Stages Summary
| Stage | Status | Duration | Details |
|---|---|---|---|
| Linting (Ruff) | PASS | `0.03s` | All ruff rules passed. |
| Static Typing (Mypy) | PASS | `0.41s` | 51 source files type checked. |
| Claims Ledger Verification | PASS | `0.04s` | Ledger hashes and source provenance verified. |
| Documentation Claims Audit | PASS | `0.03s` | Documentation claims verified against ledger (0 violations). |
| Repository Integrity Checks | PASS | `1.38s` | All integrity checks passed. |
| Privacy by Design Audit (TC-18) | PASS | `0.01s` | Evidence directory verified with 0 face violations (0 findings). |
| Offline Evaluation (TC-21, TC-22) | PASS | `0.21s` | Offline evaluation on synthetic fixture completed (SIMULATED). |
| Test Suite Execution | PASS | `4.47s` | Pytest suite executed (101 tests, sim=1, real=1, hardware=2). |

## Evidence & Claims Verification Matrix

| Item / Claim | Measured on this machine | Simulated / synthetic | Pending hardware run | Status | Source / Proof |
|---|---|---|---|---|---|
| Python Test Suite (101 tests) | YES | No | No | MEASURED | `pytest` run |
| Static Typing & Linting | YES | No | No | MEASURED | `mypy` + `ruff` |
| Claims Ledger Verification | YES | No | No | MEASURED | `evidence/ledger.yaml` |
| Documentation Claims Audit | YES | No | No | MEASURED | `tools/audit_claims.py` |
| Privacy by Design Audit | YES | No | No | MEASURED | `tools/privacy_audit.py` (0 faces leaked) |
| Offline Incident Detection (P/R/F1) | No | YES | No | SIMULATED | `reports/simulated/eval_simulated.json` |
| PipeGen Stage 5 Export | No | No | YES | PENDING | `pipegen/export/` (awaiting hardware run) |
| TensorRT FP32 / FP16 / INT8 Benchmarks | No | No | YES | PENDING | `evidence/hardware/` (awaiting GPU run) |
| Hardware Platform Telemetry | No | No | YES | PENDING | `evidence/hardware/` (awaiting tegrastats) |

## Hardware-Dependent Verification Notice
Test cases `TC-03` (environment readiness), `TC-04` (PipeGen export), and `TC-29` (hardware benchmark) require physical GPU access and PipeGen execution.
They skip cleanly on CPU-only machines (`make verify-hardware`). The booth hardware checklist is documented in `docs/RUNBOOK.md`.

## Final Judgement
**SiteSentinel backend meets all automated architectural, domain, privacy, and integrity requirements. Hardware profiling and PipeGen exports are tracked honestly as PENDING until physical booth check-in.**
