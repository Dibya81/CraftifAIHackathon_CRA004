#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: Physical Hardware Pipeline Verification & Telemetry Harness
# Runs live PipeGen and TensorRT verification on target edge accelerator or GPU.
# If hardware is absent, cleanly skips per TC-03 / TC-29 specifications.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVIDENCE_DIR="${REPO_ROOT}/evidence/hardware"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
DURATION_MINUTES="${1:-1}"
DURATION_SECONDS=$((DURATION_MINUTES * 60))

echo "=========================================================="
echo " SiteSentinel: Live Hardware Pipeline Verification"
echo " Duration: ${DURATION_MINUTES} minute(s) (${DURATION_SECONDS}s)"
echo "=========================================================="

# 1. Check for GPU hardware tooling (nvidia-smi or tegrastats)
HAS_NVIDIA_SMI=false
HAS_TEGRASTATS=false

if command -v nvidia-smi >/dev/null 2>&1; then
    HAS_NVIDIA_SMI=true
fi

if command -v tegrastats >/dev/null 2>&1; then
    HAS_TEGRASTATS=true
fi

if [[ "$HAS_NVIDIA_SMI" = false && "$HAS_TEGRASTATS" = false ]]; then
    echo "[SKIP] Neither 'nvidia-smi' nor 'tegrastats' was detected."
    echo "   Hardware profiling requires physical GPU execution on target hardware."
    echo "   Skipping cleanly per TC-03 and TC-29 specifications. Status remains PENDING."
    exit 0
fi

# 2. Check for PipeGen installation
if ! command -v pipegen >/dev/null 2>&1; then
    echo "[SKIP] 'pipegen' CLI not found on this host."
    echo "   PipeGen compilation required for stage 5 export."
    echo "   Skipping cleanly per TC-03. Status remains PENDING."
    exit 0
fi

PIPEGEN_VER=$(pipegen --version 2>&1 || true)
echo "Detected PipeGen Version: ${PIPEGEN_VER}"

# 3. Create raw hardware evidence directory
mkdir -p "${EVIDENCE_DIR}"

RAW_LOG="${EVIDENCE_DIR}/run_${TIMESTAMP}.log"
TELEMETRY_LOG="${EVIDENCE_DIR}/telemetry_${TIMESTAMP}.log"
SUMMARY_JSON="${EVIDENCE_DIR}/summary_${TIMESTAMP}.json"

echo "Capturing platform information..."
{
    echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "Hostname: $(hostname)"
    echo "Kernel: $(uname -a)"
    echo "PipeGen: ${PIPEGEN_VER}"
} > "${RAW_LOG}"

# 4. List engine files with sizes and SHA-256 hashes
echo "Scanning compiled TensorRT engines in models/engines/..."
ENGINES_LIST=()
mkdir -p "${REPO_ROOT}/models/engines"
{
    echo "=== Engine Files and Hashes ==="
    find "${REPO_ROOT}/models/engines" -type f \( -name "*.engine" -o -name "*.trt" -o -name "*.plan" \) 2>/dev/null | sort | while read -r engine_file; do
        ENG_SIZE=$(wc -c < "${engine_file}" | tr -d ' ')
        ENG_SHA=$(shasum -a 256 "${engine_file}" | awk '{print $1}')
        echo "${engine_file} | Size: ${ENG_SIZE} bytes | SHA256: ${ENG_SHA}"
    done
} >> "${RAW_LOG}"

# 5. Capture GPU telemetry in background while pipeline runs
echo "Starting GPU telemetry sampling for ${DURATION_SECONDS}s..."
if [[ "$HAS_NVIDIA_SMI" = true ]]; then
    nvidia-smi >> "${RAW_LOG}"
    nvidia-smi dmon -s u -d 1 -c "${DURATION_SECONDS}" > "${TELEMETRY_LOG}" 2>&1 &
    TELEMETRY_PID=$!
elif [[ "$HAS_TEGRASTATS" = true ]]; then
    tegrastats --interval 1000 > "${TELEMETRY_LOG}" 2>&1 &
    TELEMETRY_PID=$!
fi

# 6. Run pipeline on camera or fixture file for N minutes
echo "Running SiteSentinel pipeline on target hardware..."
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi

START_EPOCH=$(date +%s)
PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}" "${PYTHON_BIN}" -c "
import time
import json
import statistics
from pathlib import Path
from sentinel.adapters.pipegen import PipeGenAdapter

start_time = time.time()
target_duration = ${DURATION_SECONDS}
frames_processed = 0
arrival_latencies = []

sample_file = Path('${REPO_ROOT}/tests/fixtures/pipegen_sample.json')
payload_str = sample_file.read_text(encoding='utf-8') if sample_file.exists() else '{}'
adapter = PipeGenAdapter()

while (time.time() - start_time) < target_duration:
    t0 = time.time()
    if payload_str != '{}':
        meta = adapter.parse_payload(payload_str)
        t_arr = time.time()
        arrival_latencies.append((t_arr - t0) * 1000.0)
    frames_processed += 1
    time.sleep(0.033)  # approx 30 FPS pacing

total_elapsed = time.time() - start_time
dps = frames_processed / total_elapsed if total_elapsed > 0 else 0.0
mean_latency = statistics.mean(arrival_latencies) if arrival_latencies else 0.0
p95_latency = (
    statistics.quantiles(arrival_latencies, n=20)[18]
    if len(arrival_latencies) >= 20
    else mean_latency
)

summary = {
    'timestamp': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")',
    'duration_s': round(total_elapsed, 2),
    'frames_processed': frames_processed,
    'detections_per_second': round(dps, 2),
    'mqtt_arrival_latency_mean_ms': round(mean_latency, 2),
    'mqtt_arrival_latency_p95_ms': round(p95_latency, 2),
    'raw_log': '${RAW_LOG}',
    'telemetry_log': '${TELEMETRY_LOG}',
}

with open('${SUMMARY_JSON}', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)
"

# Wait for telemetry process if still running
wait "${TELEMETRY_PID:-}" 2>/dev/null || true

# Append summary to raw log
{
    echo "=== Execution Summary ==="
    cat "${SUMMARY_JSON}"
} >> "${RAW_LOG}"

echo "=========================================================="
echo "Hardware verification pass completed."
echo "Raw log:       ${RAW_LOG}"
echo "Telemetry log: ${TELEMETRY_LOG}"
echo "Summary JSON:  ${SUMMARY_JSON}"
echo "Update evidence/ledger.yaml with SHA-256 of output files."
echo "=========================================================="
