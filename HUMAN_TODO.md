# SiteSentinel — Hackathon Audit & Repair: Phased TODO

> **Rule:** No number, badge, or status in any document without a raw source
> file + SHA-256 in `evidence/ledger.yaml`. Every metric is MEASURED, SIMULATED,
> or PENDING — never promoted.

Legend: `[AI]` = can be done by AI/code | `[HUMAN]` = requires a person | `[HW]` = requires hardware

---

## Phase 1 — Purge Fabricated Evidence & Create Ledger
**Goal:** Nothing false remains in the repo.
**Gate:** `tools/ledger.py verify` exits 0; `tools/audit_claims.py` exits 0.

- [x] `[AI]` Create `evidence/ledger.yaml` with honest MEASURED / SIMULATED / PENDING entries
- [x] `[AI]` Defect 1: Delete invented numbers from `reports/engine_inputs.yaml` (replace all values with null, status PENDING)
- [x] `[AI]` Defect 1: Rewrite `tools/engine_report.py` — refuse rendering when source_file or sha256 is missing; output "PENDING: no engine built yet"
- [x] `[AI]` Defect 1: Regenerate `reports/engine_comparison.md` and `.json` as honest PENDING documents
- [x] `[AI]` Defect 5: Move `reports/pipeline_ir.png` to `docs/diagrams/architecture.png`; add PENDING placeholder note at `evidence/pipegen/pipeline_ir.png`
- [x] `[AI]` Defect 6: Remove `.pipegen/` mirror directory; make `tools/judge.py` fail loudly when `pipegen/export/` contains only `.gitkeep`
- [x] `[AI]` Defect 7: Move 18 timestamped eval report pairs into `reports/simulated/`; stamp each header SIMULATED; keep one canonical `reports/simulated/eval_simulated.json`
- [x] `[AI]` Defect 7: Move simulator clip + labels to `tests/fixtures/` (or `data/simulated/`); stamp README as SIMULATED
- [x] `[AI]` Defect 9: Delete `skills-lock.json` and `bin/` directory; add `LICENSE` (MIT)
- [x] `[AI]` Defect 9: Replace all hard-coded badges with a single CI badge placeholder; remove emojis from all docs
- [x] `[AI]` Create `tools/ledger.py verify` command (recompute hashes, fail on missing sources, fail on MEASURED with gpu=none)

---

## Phase 2 — Rewrite README, SUBMISSION, JUDGE_REPORT
**Goal:** Every claim in public-facing docs is ledger-sourced or architectural description.
**Gate:** `tools/audit_claims.py` passes with 0 violations.

- [x] `[AI]` Defect 2: Rewrite `README.md` — max 250 lines, ordered as spec, no emojis, no hardware names, no un-ledgered numbers, one CI badge
- [x] `[AI]` Defect 3: Rewrite `SUBMISSION.md` — author = human team member(s), relative links only, all numbers sourced from ledger
- [x] `[AI]` Defect 4: Rewrite `JUDGE_REPORT.md` — SIM/REAL/PENDING columns; delete "zero simulated or fabricated metrics"; no hard-coded verdict
- [x] `[AI]` Create `tools/audit_claims.py` — scans all .md files for banned phrases and bare metric patterns not in generated blocks
- [x] `[AI]` Update `Makefile` `judge` target to run: ledger verify + audit_claims + pytest + lint in order
- [x] `[AI]` Author set to "Dibya Bhusal" in SUBMISSION.md

---

## Phase 3 — Duplicate Module Cleanup
**Goal:** One canonical implementation per module; no file that only re-exports without adding value.
**Gate:** `pytest` still green; `tests/test_no_duplicate_modules.py` passes.

- [x] `[AI]` Defect 8: Determine canonical entry point — `src/sentinel/api.py` (751 lines) vs `src/sentinel/interfaces/api/app.py` (525 lines); delete the duplicate; fix all imports
- [x] `[AI]` Add `tests/test_no_duplicate_modules.py` — fails if two files implement the same public symbols or a file under 30 lines only re-exports
- [x] `[AI]` Defect 9: Merge `tools/soak.py` vs `tools/soak_test.py`; merge `test_benchmark.py` vs `tests/perf/` duplication
- [x] `[AI]` Run `pytest` — confirm 85 passing with zero duplicates

---

## Phase 4 — Baseline Detector & Real Footage Tooling
**Goal:** System can detect on real video without PipeGen; evaluation tooling is honest.
**Gate:** `tests/test_baseline_detector.py` skips cleanly when weights absent (not xfail); `eval/evaluate.py` refuses PASS on <30 events or SIMULATED data.

- [x] `[AI]` Create `src/sentinel/adapters/baseline_detector.py` — ONNX Runtime CPU detector, same detection schema as PipeGen adapter, clearly labelled baseline
- [x] `[AI]` Create `scripts/fetch_baseline_model.sh` — downloads permissively-licensed ONNX weights, verifies SHA-256, refuses >25 MB commits
- [x] `[AI]` Create `tests/test_baseline_detector.py` — marker `real`, skips with explicit reason when weights absent
- [x] `[AI]` Create `tests/fixtures/pipegen_real_sample/README.md` (PENDING) + test that skips with "PENDING real PipeGen sample"
- [x] `[AI]` Create `scripts/ingest_pipegen_export.sh` — copies export to `pipegen/export/`, writes `pipegen/export.sha256`, records PipeGen version, updates ledger
- [x] `[AI]` Create `docs/DATA_PROTOCOL.md` — camera setup, labelling protocol, dev/test split, test SHA-256 locked in ledger before any threshold tuning
- [x] `[AI]` Rewrite `eval/evaluate.py` — add Wilson 95% CI, per-rule metrics, latency p95, false-alarms/hr, list of every miss; refuse PASS when events <30 or data is SIMULATED
- [x] `[AI]` Create `reports/failure_analysis.md` generator (empty until real data; generator + tests exist)
- [ ] `[HUMAN]` **ACTION NEEDED:** Record real site footage following `docs/DATA_PROTOCOL.md`
- [ ] `[HUMAN]` **ACTION NEEDED:** Run `tools/label_clip.py` on footage; commit human-reviewed labels

---

## Phase 5 — Hash-Chained Incident Log & Explainability
**Goal:** Tamper-evident log; every incident stores why it fired.
**Gate:** `sentinel verify-log` exits non-zero on any chain break; explanation tests pass.

- [x] `[AI]` Section 6: Add `prev_hash` + `hash` (SHA-256 over canonical JSON + prev_hash) to each line in `logs/incidents.jsonl`
- [x] `[AI]` Add `sentinel verify-log` CLI — non-zero exit on any chain break, db cross-check
- [x] `[AI]` Add tests: edit / delete / reorder / truncate attack on chain
- [x] `[AI]` Commit `samples/incidents_sample.jsonl` — small verified chain for CI
- [x] `[AI]` Add `GET /api/system/log-integrity` endpoint + tests
- [x] `[AI]` Add dashboard "Log chain intact: N incidents" badge (or "Chain broken at line X")
- [x] `[AI]` Section 7: Store per-incident explanation — rule name, thresholds, frames window, per-frame detection confidences, zone, timer values
- [x] `[AI]` Add incident detail timeline in dashboard showing the explanation
- [x] `[AI]` Add tests: explanation reproduces the decision when replayed

---

## Phase 6 — Hardware/Engine Tooling & Runbook
**Goal:** Scripts capture real evidence automatically on GPU; runbook tells a human exactly what to do.
**Gate:** Scripts are tested with synthetic fixtures; `docs/RUNBOOK.md` is a numbered checklist.

- [x] `[AI]` Rewrite `scripts/verify_hardware.sh` — check `pipegen --version`, list engine files with hashes, run pipeline for N minutes, capture `nvidia-smi dmon` / `tegrastats`, write raw logs + summary to `evidence/hardware/` (no hand-typed numbers)
- [x] `[AI]` Rewrite `tools/engine_report.py` — parse real PipeGen speed reports; add fixture-based parser tests (`*_fixture.*` files clearly synthetic)
- [x] `[AI]` Create `docs/RUNBOOK.md` — booth-day numbered checklist: install PipeGen, run stages, which screenshots to take, which files to copy, expected outputs
- [ ] `[HUMAN+HW]` **ACTION NEEDED:** Run `scripts/verify_hardware.sh` on GPU machine with PipeGen installed
- [ ] `[HUMAN+HW]` **ACTION NEEDED:** Commit raw logs to `evidence/hardware/`; run `tools/ledger.py verify` to promote PENDING → MEASURED
- [ ] `[HUMAN+HW]` **ACTION NEEDED:** Capture real PipeGen IR screenshot; commit to `evidence/pipegen/pipeline_ir.png`

---

## Phase 7 — Dashboard Evidence Screen & Screenshot Cleanup
**Goal:** No mock content in production bundle; Evidence screen shows ledger; screenshots labeled with mode.
**Gate:** Evidence screen tests pass; axe zero serious violations; screenshots filenames include mode.

- [x] `[AI]` Defect 10: Add Evidence screen to dashboard — reads `/api/evidence/ledger`, shows each claim with status chip, source link, hash, "Verify" button (re-hashes server-side)
- [x] `[AI]` Add `GET /api/evidence/ledger` endpoint + tests
- [x] `[AI]` Confirm no "Design" route in production build; confirm mode banner is accurate
- [x] `[AI]` Defect 11: Trim `evidence/submission_bugs_and_failures/` — keep only genuine reproducible failures with file + one-line cause; cut marketing entries
- [x] `[AI]` Defect 10: Rename demo video with `-simulated` suffix; update `evidence/README.md` and README captions
- [ ] `[HUMAN]` **ACTION NEEDED:** Run dashboard in LIVE (backend down), REPLAY (baseline), and SIMULATED modes; capture screenshots named `dashboard-<mode>.png`; run axe

---

## Phase 8 — Final Gate (paste real outputs)
**Goal:** All checks green; final table and ledger summary committed.

- [x] `[AI]` Run `make judge` — paste actual terminal output
- [x] `[AI]` Run `tools/ledger.py verify` — paste actual terminal output
- [x] `[AI]` Run `tools/audit_claims.py` — paste actual terminal output
- [x] `[AI]` Run `npm run check` in `dashboard/` — paste actual terminal output
- [x] `[AI]` Print final defect table: what was wrong → what changed → what is PENDING
- [x] `[AI]` Print ledger summary: count of MEASURED / SIMULATED / PENDING
- [ ] `[HUMAN]` Final review and sign-off

---

## HUMAN Actions Summary (ordered by urgency)

| Priority | Phase | Action |
|----------|-------|--------|
| 1 | Phase 4 | Record real site footage following docs/DATA_PROTOCOL.md |
| 2 | Phase 4 | Label footage with tools/label_clip.py; commit human-reviewed labels |
| 3 | Phase 6 | Run scripts/verify_hardware.sh on GPU+PipeGen machine |
| 4 | Phase 6 | Ingest real export: ./scripts/ingest_pipegen_export.sh <export_path> |
| 5 | Phase 6 | Commit raw hardware logs; re-run tools/ledger.py verify |
| 6 | Phase 6 | Capture PipeGen IR screenshot; commit to evidence/pipegen/pipeline_ir.png |
| 7 | Phase 7 | Run dashboard in 3 modes; capture labeled screenshots |
| 8 | Phase 8 | Final review and sign-off |

---

## Current State Snapshot

| Claim | Previous Value | Honest Status |
|-------|---------------|---------------|
| Test count | 87 | MEASURED (101 collected, 99 passed, 2 skipped pending HW) |
| Eval precision/recall/F1 | 100% / 100% / 1.0 | SIMULATED (simulator data only) |
| Engine FPS FP32 | 11.2 FPS | PENDING (invented, deleted) |
| Engine FPS FP16 | 24.7-24.8 FPS | PENDING (invented, deleted) |
| Engine FPS INT8 | 31.4 FPS | PENDING (invented, deleted) |
| INT8 speedup | 1.27x | PENDING (invented, deleted) |
| VRAM reduction | 46.7% / -789 MB | PENDING (invented, deleted) |
| PipeGen export | "Frozen & Verified" | PENDING (only .gitkeep; fails check loudly) |
| Hardware platform | Jetson Orin Nano | PENDING (no raw log, name removed) |
| Pipeline IR screenshot | reports/pipeline_ir.png | PENDING (was architecture diagram) |
| Baseline detector | — | MEASURED (YOLOv8n ONNX baseline on CPU) |
| Hash-chained log | — | MEASURED (SHA-256 chain + verify-log + API) |
| Explainability per incident | — | MEASURED (decision timeline + replay test) |
| Evidence dashboard screen | — | MEASURED (reads ledger + server verify) |
