# SiteSentinel: Failure Modes & Root Cause Analysis

- **Evaluation Run**: `2026-10-19T03:00:08.195821`
- **Source Clip**: `data/simulated/site01-simulated.mp4`
- **Labels File**: `data/simulated/site01-labels.json`
- **Data Provenance**: `SIMULATED`

## 1. Summary of Discrepancies
- **Missed Violations (False Negatives)**: 3
- **False Alarms (False Positives)**: 4
- **False Alarm Rate**: 757.89 events / hour
- **Latency p95**: 0.00 s

## 2. Missed Violation Incidents
| Index | Rule | Interval | Track | Zone | Triage Notes |
|---|---|---|---|---|---|
| 0 | `NO_HELMET` | 2.0s - 6.0s | 1 | press-area | Short interval or track association delay |
| 1 | `ZONE_INTRUSION` | 8.0s - 12.0s | 2 | crane-drop | Short interval or track association delay |
| 2 | `DANGER_DWELL` | 13.0s - 18.0s | 2 | crane-drop | Short interval or track association delay |

## 3. False Alarm Incidents
| Index | Time | Rule | Severity | Track | Zone | Confidence | Triage Notes |
|---|---|---|---|---|---|---|---|
| 0 | 2.0s | `NO_HELMET` | MEDIUM | 2 | walkway | 0.92 | Transient detection flicker |
| 1 | 9.2s | `ZONE_INTRUSION` | HIGH | 3 | press-area | 0.95 | Transient detection flicker |
| 2 | 11.0s | `ZONE_INTRUSION` | HIGH | 4 | crane-drop | 0.92 | Transient detection flicker |
| 3 | 16.0s | `DANGER_DWELL` | HIGH | 4 | crane-drop | 0.92 | Transient detection flicker |

## 4. Root Cause Recommendations
1. **Debounce Tuning**: Increase `min_duration_s` from 1.0s to 1.5s if false alarm rate exceeds 2.0/hr.
2. **IoA Association**: Adjust PPE intersection-over-area threshold for workers viewed at oblique camera angles.
3. **Physical Validation**: Run evaluation against ≥ 30 physical events on target hardware to lift SIMULATED status.
