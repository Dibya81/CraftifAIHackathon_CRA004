# SiteSentinel: Evidence Directory Inventory

Every media asset and data file in this directory is stamped with its operational mode.
Per the claims ledger (`evidence/ledger.yaml`), no asset is presented as live hardware evidence without a corresponding signed SHA-256 log from physical execution.

---

## Inventory and Operational Modes

| File / Subdirectory | Mode | Description |
|---|---|---|
| `demo_walkthrough_1_to_3_min-simulated.mp4` | **SIMULATED** | 3-minute control room walkthrough recorded against `sentinel run --sim` simulated stream. |
| `sample/sample-no-helmet-001.mp4` | **SIMULATED** | Standardized 10-second test incident clip generated from synthetic pipeline. Verified 100% face-blurred by privacy audit (`tools/privacy_audit.py`). |
| `sample/sample-no-helmet-001.jpg` | **SIMULATED** | Privacy-masked thumbnail snapshot associated with sample incident. |
| `screenshots/` | **SIMULATED** | UI captures of control room dashboard views running with simulated OpenCV generator (`sentinel run --sim`). |
| `submission_bugs_and_failures/` | **REPRODUCIBLE BUG** | Genuine software failures, crashes, and failing tests encountered during development, with reproduction steps and root causes. |
| `hardware/` | **PENDING** | Reserved for raw logs from physical GPU execution (`scripts/verify_hardware.sh`). Empty until hardware run. |
| `pipegen/` | **PENDING** | Reserved for real PipeGen Pipeline IR node graph capture (`pipeline_ir.png`) and stage 5 exports. |
| `ledger.yaml` | **LEDGER** | Cryptographic ledger of all metrics, statuses, commands, and SHA-256 hashes. |

---

## Reproducibility

To re-verify hashes across all evidence files:
```bash
python tools/ledger.py verify
```
