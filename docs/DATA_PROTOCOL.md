# SiteSentinel: Physical Data Collection and Evaluation Protocol

This protocol defines the standard operating procedures for capturing, labeling, splitting, and cryptographically locking perception and rule evaluation data for SiteSentinel.

---

## 1. Camera Setup, Lighting, and Field of View

Industrial CCTV or edge sensor placement must satisfy the following geometric and environmental constraints:

### Geometric Constraints
| Parameter | Specification | Purpose |
|---|---|---|
| Mounting Height | 3.0 m to 5.0 m above floor grade | Provides clear oblique field of view; minimizes occlusions |
| Downward Tilt Angle | 30 deg to 45 deg from horizontal | Minimizes horizon glare; ensures reliable foot-point projection |
| Video Resolution | 1920x1080 (1080p) or 1280x720 (720p) | Maintains adequate pixel density for PPE detection at 15 m distance |
| Frame Rate | 25 FPS to 30 FPS constant bitrate | Required for multi-frame debounce and velocity estimation |
| Sensor Interface | RTSP over Ethernet or local V4L2 device | Standard industrial stream transport |

### Distance and Range Coverage
- **Near Range (2 m - 5 m)**: High-resolution PPE detail, head region verification, face blurring validation.
- **Mid Range (5 m - 10 m)**: Primary operating zone for walkway crossings and restricted perimeter entries.
- **Far Range (10 m - 15 m)**: Boundary detection testing; minimum person bounding box height must exceed 60 pixels.

### Lighting Conditions to Record
Clips must include operational variations across:
1. **Direct Sunlight / High Contrast**: Harsh shadows near equipment, glare on hard hats.
2. **Overhead Industrial Lighting**: High-bay LED/fluorescent illumination (300 - 500 lux).
3. **Low-Light / Shift Change**: Dusk or dim transitional lighting (50 - 150 lux) requiring high-visibility vest retro-reflectivity.

### Behavioral Actor Sequences
For each evaluation scenario, actors must execute clear state transitions:
- **Helmet On/Off**: Actor enters scene wearing helmet, pauses, removes helmet for >= 5 seconds, replaces helmet.
- **Vest On/Off**: Actor unzips or removes high-vis vest while inside monitored zone.
- **Zone Entries**: Actor transitions from `safe` walkway into `restricted` perimeter and `danger` machinery zone, remaining for defined intervals.

---

## 2. Privacy by Design (TC-18)

Per European and OSHA worker privacy standards:
1. Real-time inference must run entirely on-premise on local compute; no video stream is sent to external clouds.
2. If evidence thumbnails or video clips are exported to disk or dashboard, facial regions must be redacted prior to storage.
3. Facial recognition, biometric fingerprinting, and worker identification are strictly prohibited. The system assigns anonymous integer tracking IDs (`track_id`) scoped strictly to active track life cycles.

---

## 3. Labeling with `tools/label_clip.py`

Evaluation clips are paired with a canonical ground-truth JSON file generated using the labeling CLI:

### Command Syntax
```bash
python tools/label_clip.py --clip data/test_clips/<clip_name>.mp4 \
  --out data/labelled/<clip_name>.json \
  --add "NO_HELMET:<start_s>:<end_s>:<track_id>:<zone>" \
  --add "ZONE_INTRUSION:<start_s>:<end_s>:<track_id>:<zone>"
```

### Example
```bash
python tools/label_clip.py --clip data/test_clips/site01.mp4 \
  --out data/labelled/site01_dev.json \
  --add "NO_HELMET:2.0:6.0:1:press-area" \
  --add "ZONE_INTRUSION:8.0:12.0:2:crane-drop"
```

### Violation Interval Schema
- `type`: Must match one of `NO_HELMET`, `NO_VEST`, `ZONE_INTRUSION`, `DANGER_DWELL`.
- `start_s`: The precise timestamp in seconds where the condition first materialized.
- `end_s`: The timestamp where the condition ceased (worker put on PPE, or exited the restricted area).
- `track_id`: Optional subject identifier.
- `zone`: Identifier of the polygonal zone (required for `ZONE_INTRUSION` and `DANGER_DWELL`).

---

## 4. Dataset Partitioning (Dev vs. Locked Test)

To prevent data contamination and overfitting:
1. **Site Disjointness**: Training and development validation clips must originate from different physical locations or different camera viewpoints than the evaluation test suite.
2. **Temporal Disjointness**: If recorded at the same site, test clips must be recorded during distinct shifts separated by at least 24 hours.
3. **Partition Naming**:
   - Development set: `data/labelled/*_dev.json`
   - Evaluation test set: `data/labelled/*_test.json`
4. **Threshold Tuning Refusal**:
   The threshold sweep engine (`eval/evaluate.py`) strictly enforces that parameter sweeps and tuning can only execute against development labels (`*_dev.json`). Attempting to sweep thresholds against `*_test.json` raises a `Data Protocol Integrity Violation` error.
5. **Event Qualification Threshold**: For a benchmark to qualify for production `MEASURED` acceptance, the test split must contain a minimum of 30 distinct violation events across all four rule types.

---

## 5. Cryptographic Ledger Locking

Before any test report is published or evaluated:
1. The raw `.mp4` video clip is hashed:
   ```bash
   shasum -a 256 data/test_clips/<clip>.mp4
   ```
2. The ground-truth annotation `.json` is formatted with sorted keys and hashed:
   ```bash
   shasum -a 256 data/labelled/<clip>.json
   ```
3. Both entries are recorded in `evidence/ledger.yaml` under their corresponding claim keys with status `MEASURED`.
4. Integrity is verified with:
   ```bash
   python tools/ledger.py verify
   ```
If any byte in the video or labels changes after evaluation, `tools/ledger.py verify` fails and halts the verification gate.
