#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: Make Offline Bundle
# Packages dependencies, wheels, npm assets, and baseline models for booth day
# when venue Wi-Fi may be unreliable or absent.
# Output target: offline/ (git-ignored)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OFFLINE_DIR="${REPO_ROOT}/offline"
MANIFEST_FILE="${OFFLINE_DIR}/manifest.sha256"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

echo "=================================================================="
echo " SiteSentinel: Generating Offline Bundle"
echo " Target directory: ${OFFLINE_DIR}"
echo "=================================================================="

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] Would create directory structure:"
    echo "  - ${OFFLINE_DIR}/wheels (Python packages from requirements.txt)"
    echo "  - ${OFFLINE_DIR}/npm (Dashboard dependencies cache)"
    echo "  - ${OFFLINE_DIR}/models (Baseline ONNX weights)"
    echo "  - ${OFFLINE_DIR}/fonts (Inter and fallback UI typography)"
    echo "  - ${MANIFEST_FILE} (SHA-256 integrity manifest)"
    exit 0
fi

mkdir -p "${OFFLINE_DIR}/wheels"
mkdir -p "${OFFLINE_DIR}/npm"
mkdir -p "${OFFLINE_DIR}/models"
mkdir -p "${OFFLINE_DIR}/fonts"

# 1. Download Python wheels
echo ">>> 1. Downloading Python wheels from requirements.txt..."
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" -m pip download \
    --dest "${OFFLINE_DIR}/wheels" \
    --requirement "${REPO_ROOT}/requirements.txt" \
    --prefer-binary 2>&1 | tail -n 10 || echo "[WARN] Some wheels could not be pre-downloaded"

# 2. Cache npm dependencies for dashboard
echo ">>> 2. Packaging npm cache for dashboard..."
if command -v npm >/dev/null 2>&1; then
    (
        cd "${REPO_ROOT}/dashboard"
        if [[ -d "node_modules" ]]; then
            tar -czf "${OFFLINE_DIR}/npm/node_modules_cache.tar.gz" node_modules
            echo "Archived dashboard/node_modules into offline bundle."
        fi
    )
fi

# 3. Cache baseline models
echo ">>> 3. Checking baseline models..."
if [[ -f "${REPO_ROOT}/models/baseline/detector.onnx" ]]; then
    cp "${REPO_ROOT}/models/baseline/detector.onnx" "${OFFLINE_DIR}/models/"
    echo "Copied detector.onnx to offline/models/"
else
    echo "detector.onnx not present locally; will be downloaded on first run via scripts/download_baseline_model.sh"
fi

# 4. Generate SHA-256 Manifest
echo ">>> 4. Computing offline manifest hashes..."
(
    cd "${OFFLINE_DIR}"
    find . -type f ! -name "manifest.sha256" | sort | while read -r f; do
        if command -v shasum >/dev/null 2>&1; then
            shasum -a 256 "${f}"
        elif command -v sha256sum >/dev/null 2>&1; then
            sha256sum "${f}"
        fi
    done > "${MANIFEST_FILE}"
)

echo "=================================================================="
echo " Offline bundle successfully generated at ${OFFLINE_DIR}"
echo " Total files in manifest: $(wc -l < "${MANIFEST_FILE}" | tr -d ' ')"
echo " To install on edge target: ./scripts/install_offline.sh"
echo "=================================================================="
