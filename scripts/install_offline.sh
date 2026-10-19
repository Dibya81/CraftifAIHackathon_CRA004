#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: Install Offline Bundle
# Installs Python packages, dashboard cache, and restores model weights from
# pre-downloaded offline/ bundle without external internet access.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OFFLINE_DIR="${REPO_ROOT}/offline"
MANIFEST_FILE="${OFFLINE_DIR}/manifest.sha256"

echo "=================================================================="
echo " SiteSentinel: Installing from Offline Bundle"
echo " Source directory: ${OFFLINE_DIR}"
echo "=================================================================="

if [[ ! -d "${OFFLINE_DIR}" ]]; then
    echo "Error: ${OFFLINE_DIR} does not exist. Run scripts/make_offline_bundle.sh first."
    exit 1
fi

# 1. Verify manifest integrity
if [[ -f "${MANIFEST_FILE}" ]]; then
    echo ">>> 1. Verifying bundle integrity..."
    (
        cd "${OFFLINE_DIR}"
        if command -v shasum >/dev/null 2>&1; then
            shasum -a 256 -c manifest.sha256 || echo "[WARN] Some file checksums differed"
        elif command -v sha256sum >/dev/null 2>&1; then
            sha256sum -c manifest.sha256 || echo "[WARN] Some file checksums differed"
        fi
    )
fi

# 2. Install Python wheels
echo ">>> 2. Installing Python wheels offline..."
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    python3 -m venv "${REPO_ROOT}/.venv"
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
fi

if [[ -d "${OFFLINE_DIR}/wheels" ]]; then
    "${PYTHON_BIN}" -m pip install \
        --no-index \
        --find-links="${OFFLINE_DIR}/wheels" \
        -r "${REPO_ROOT}/requirements.txt"
fi

# 3. Restore dashboard node_modules
if [[ -f "${OFFLINE_DIR}/npm/node_modules_cache.tar.gz" ]]; then
    echo ">>> 3. Restoring dashboard node_modules..."
    mkdir -p "${REPO_ROOT}/dashboard"
    tar -xzf "${OFFLINE_DIR}/npm/node_modules_cache.tar.gz" -C "${REPO_ROOT}/dashboard"
fi

# 4. Restore baseline models
if [[ -f "${OFFLINE_DIR}/models/detector.onnx" ]]; then
    echo ">>> 4. Restoring baseline detector model..."
    mkdir -p "${REPO_ROOT}/models/baseline"
    cp "${OFFLINE_DIR}/models/detector.onnx" "${REPO_ROOT}/models/baseline/"
fi

echo "=================================================================="
echo " Offline installation complete. Running doctor verification..."
echo "=================================================================="
"${PYTHON_BIN}" -m sentinel.interfaces.cli.main doctor
