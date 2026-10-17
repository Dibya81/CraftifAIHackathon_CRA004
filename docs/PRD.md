# SiteSentinel: Product Requirements Document

Version 1.0 | Embedded SF, Track A (PipeGen) | Scope: software only | Bonus target: Edge Optimization

## 1. Summary
SiteSentinel turns a site camera into a real-time safety officer. A PipeGen-generated DeepStream pipeline (TensorRT) detects people, hard hats and high-vis vests. A rule engine raises incidents for missing PPE and hazard-zone intrusions, publishes them over MQTT, writes a JSON incident log, saves face-blurred evidence clips, and feeds a live dashboard. An evaluation harness reports precision, recall and alert latency, and an FP16 vs INT8 report documents the edge trade-off.

## 2. Problem and users
Workers enter hazard zones or skip PPE and nobody notices until an incident. Manual CCTV monitoring does not scale.
- Safety officer: wants alerts only when something real happens, with evidence.
- Site manager: wants trends by zone, shift and violation type.
- Worker: must not be identifiable in stored evidence.

## 3. Goals and non-goals
Goals
1. Real-time detection of person, hard hat and vest (target at least 25 FPS FP16 at 1080p on the demo GPU).
2. Incidents for NO_HELMET, NO_VEST, ZONE_INTRUSION and DANGER_DWELL.
3. Delivery over MQTT plus an append-only `incidents.jsonl`.
4. Privacy-first evidence: faces blurred before any frame is written to disk.
5. Live dashboard and a measurable accuracy report.

Non-goals
- Worker identification, face recognition, attendance.
- Cloud processing; everything runs locally and offline.
- Multi-site fleet management.
- Hardware actuation (ESP32 Closed Loop is out of scope for this version; see Future work).

## 4. Hackathon alignment
| Requirement | How SiteSentinel meets it |
|---|---|
| Full PipeGen flow (5 stages) | Requirement, Pipeline IR, Model, Compiler, Run all executed; `pipegen/` holds the frozen requirement and export |
| TensorRT engine + speed report | FP16 and INT8 engines, reports saved in `reports/` |
| Live run | USB camera, RTSP, or video file on an NVIDIA GPU machine |
| Actionable output | MQTT incident feed, JSON log, evidence clips, dashboard |
| Deep integration | Product runs on PipeGen outputs; export folder committed untouched |
| Edge Optimization bonus | FP32/FP16/INT8 table: FPS, latency, power, accuracy |

## 5. Functional requirements
| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Build the pipeline through all five PipeGen stages | Must |
| FR-2 | Accept video file, USB camera or RTSP, selectable at run time | Must |
| FR-3 | Compile at least one model to TensorRT and keep the PipeGen speed report | Must |
| FR-4 | Detect person, hard hat, head without hat, high-vis vest | Must |
| FR-5 | Track persons with stable IDs | Must |
| FR-6 | Associate PPE boxes to a person via head and torso region overlap | Must |
| FR-7 | Polygon zones (safe, restricted, danger) from JSON config and a dashboard drawing tool | Must |
| FR-8 | Raise incident when a tracked person lacks required PPE for more than N seconds (default 2) | Must |
| FR-9 | Raise incident on restricted-zone entry; higher severity when danger-zone dwell exceeds T seconds | Must |
| FR-10 | Debounce: one incident per continuous violation per track, with a cooldown before re-alert | Must |
| FR-11 | Publish each incident to MQTT `sentinel/incidents` and append to `incidents.jsonl` | Must |
| FR-12 | Save a 10 s evidence clip (5 s before, 5 s after) with faces blurred before write | Must |
| FR-13 | Dashboard: live annotated view, incident feed, per-zone counts, hourly chart | Must |
| FR-14 | Offline evaluation script reporting precision, recall and alert latency per rule | Must |
| FR-15 | FP16 and INT8 variants with FPS, GPU power and accuracy comparison | Should |
| FR-16 | Custom PPE detector trained with Edge MLOps; ONNX parity verified | Should |
| FR-17 | Telegram or webhook forwarding for HIGH incidents | Could |

## 6. Non-functional requirements
- Latency: violation start to MQTT publish under 3 s including the 2 s debounce.
- Throughput: at least 25 FPS at 1080p FP16; INT8 measurably faster.
- Privacy: blur happens inside the pipeline branch; no unblurred face frame is persisted.
- Reliability: camera disconnect yields a health event, not a crash; processes auto-restart.
- Reproducibility: `scripts/run_demo.sh` starts everything.
- Offline: no internet needed at demo time.

## 7. Incident schema
```json
{
  "incident_id": "uuid",
  "timestamp": "ISO-8601",
  "camera_id": "cam-01",
  "type": "NO_HELMET | NO_VEST | ZONE_INTRUSION | DANGER_DWELL",
  "severity": "LOW | MEDIUM | HIGH",
  "track_id": 17,
  "zone": "press-area",
  "confidence": 0.91,
  "duration_s": 3.4,
  "evidence_clip": "evidence/2026-.../inc-uuid.mp4"
}
```

## 8. Model plan
- Baseline (week 1): catalog or Deep Search PPE detector so the pipeline works end to end early.
- Custom (weeks 5-6): fine-tune a small YOLO-family model on a public PPE dataset plus own clips; augment for brightness, blur, occlusion; keep a held-out test set from own recordings.
- Verification: Edge MLOps parity check between trained and exported ONNX; keep the report.
- INT8 calibration: 500+ diverse frames (lighting, distance), not only dataset images.

## 9. Acceptance criteria
- AC-1: 10 minutes live on a USB camera without a crash.
- AC-2: Person without helmet triggers exactly one NO_HELMET incident within 3 s; person with helmet triggers none.
- AC-3: Entering a restricted polygon triggers one ZONE_INTRUSION; re-entry after cooldown triggers a second.
- AC-4: No stored clip contains a legible face.
- AC-5: At least 85% recall and 80% precision on helmet violations on the held-out clip (adjust after the week-3 baseline).
- AC-6: INT8 faster than FP16, with the accuracy delta quantified.
- AC-7: Dashboard shows an incident within 1 s of the MQTT publish.

## 10. Evidence checklist for submission
- Pipeline IR node graph screenshot
- TensorRT speed reports (FP16, INT8)
- Repo including untouched PipeGen export folder
- Evaluation report (precision, recall, latency per rule)
- Sample `incidents.jsonl` and a blurred evidence clip
- FP32/FP16/INT8 comparison table
- 2-minute backup demo video
- Project description naming the track and bonus

## 11. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Weak detection on small or distant helmets | Fine-tune on own clips; head-region association; per-class confidence tuning |
| INT8 accuracy drop | Larger diverse calibration set; report honestly; ship FP16 as demo default if needed |
| Venue lighting differs from training | Varied lighting in training data; augmentation; recorded-clip fallback |
| Camera or RTSP fails at demo | Same pipeline on a video file; backup video |
| Judges see custom code as the product, not PipeGen | Health panel shows PipeGen engine details; export untouched; pitch walks the five stages |
| Tool access late | Use the pre-hack office hours; install early |

## 12. Eight-week plan
| Weeks | Deliverable |
|---|---|
| 1-2 | PipeGen installed, catalog person-detection pipeline live on USB camera, MQTT out; record 2+ hours of footage; label a held-out clip |
| 3-4 | Rule engine, zones, association, debounce, incident log, evaluation harness |
| 5-6 | Custom PPE model, INT8 build and comparison, face-blur branch, evidence clips |
| 7 | Dashboard, zone editor, alert forwarding, `run_demo.sh`, health panel |
| 8 | Hardening, 30-minute soak test, rehearsal, backup video, submission package |

## 13. Demo script (4 minutes)
1. Problem in 20 seconds.
2. Show the Pipeline IR and TensorRT report: "this is the engine of the product".
3. Live camera: walk in with a helmet (no alert), remove it (alert, MQTT message, dashboard updates).
4. Enter a restricted zone: HIGH incident plus blurred evidence clip.
5. Show FP16 vs INT8 table and evaluation metrics.
6. Close on privacy by design and the roadmap.

## 14. Future work
ESP32 tower light and buzzer driven by HIGH incidents (FirmGen Closed Loop bonus), multi-camera support, shift reports.
