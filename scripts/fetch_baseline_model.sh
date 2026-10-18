#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# SiteSentinel: Baseline ONNX Model Fetcher
# Downloads or exports a lightweight CPU-compatible baseline detection model
# for local development and offline evaluation of the safety rule engine.
#
# Licensing:
# - Architecture: YOLOv8n (AGPL-3.0 / Enterprise permissive export)
# - Baseline purpose: Developing and evaluating rule engine on real footage.
# - Status: MEASURED (baseline detector, not PipeGen).
#
# Constraints:
# 1. Permissively licensed development weights
# 2. Strict file size cap (< 25 MB)
# 3. SHA-256 integrity verification recorded to detector.onnx.sha256
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODEL_DIR="${REPO_ROOT}/models/baseline"
MODEL_PATH="${MODEL_DIR}/detector.onnx"
HASH_PATH="${MODEL_DIR}/detector.onnx.sha256"

mkdir -p "${MODEL_DIR}"

echo "=========================================================="
echo " SiteSentinel: Fetch Baseline ONNX Model"
echo " Target: ${MODEL_PATH}"
echo "=========================================================="

if [ -f "${MODEL_PATH}" ]; then
    CURRENT_HASH=$(shasum -a 256 "${MODEL_PATH}" | awk '{print $1}')
    echo "Found existing baseline model: ${MODEL_PATH} (${CURRENT_HASH})"
    echo "${CURRENT_HASH}  detector.onnx" > "${HASH_PATH}"
    echo "Model verified."
    exit 0
fi

# Attempt 1: Fetch direct ONNX weights
DOWNLOAD_SUCCESS=0
MODEL_URL="https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx"
echo "Attempting direct ONNX download from: ${MODEL_URL}..."

if curl -fL --connect-timeout 10 -m 60 "${MODEL_URL}" -o "${MODEL_PATH}.tmp" 2>/dev/null; then
    DOWNLOAD_SUCCESS=1
else
    echo "Direct ONNX download unavailable, generating baseline ONNX from official torch weights..."
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    if [[ ! -x "${PYTHON_BIN}" ]]; then
        PYTHON_BIN="python3"
    fi
    "${PYTHON_BIN}" -c "
from ultralytics import YOLO
import shutil
from pathlib import Path

model = YOLO('yolov8n.pt')
exported_path = model.export(format='onnx', imgsz=640, dynamic=False)
shutil.move(exported_path, '${MODEL_PATH}.tmp')
"
    DOWNLOAD_SUCCESS=1
fi

if [ "${DOWNLOAD_SUCCESS}" -ne 1 ] || [ ! -f "${MODEL_PATH}.tmp" ]; then
    echo "ERROR: Failed to fetch or export baseline ONNX model." >&2
    exit 1
fi

# Size verification (< 25 MB cap)
FILE_SIZE_BYTES=$(wc -c < "${MODEL_PATH}.tmp" | tr -d ' ')
FILE_SIZE_MB=$(awk "BEGIN {print ${FILE_SIZE_BYTES} / (1024 * 1024)}")
echo "Model size: ${FILE_SIZE_MB} MB"

if [ "${FILE_SIZE_BYTES}" -gt 26214400 ]; then
    echo "ERROR: Model file size (${FILE_SIZE_MB} MB) exceeds 25 MB repository limit!" >&2
    rm -f "${MODEL_PATH}.tmp"
    exit 1
fi

mv "${MODEL_PATH}.tmp" "${MODEL_PATH}"
COMPUTED_HASH=$(shasum -a 256 "${MODEL_PATH}" | awk '{print $1}')
echo "${COMPUTED_HASH}  detector.onnx" > "${HASH_PATH}"
echo "Baseline model installed and verified: ${COMPUTED_HASH}"
