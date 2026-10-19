#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: PipeGen Export Ingestion Tool
# Ingests raw PipeGen export deliverables, verifies integrity, runs adapter, and updates ledger.
# Includes guards against ingesting fixtures, empty trees, and missing engines.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_TARGET_DIR="${REPO_ROOT}/pipegen/export"
EXPORT_SHA_FILE="${REPO_ROOT}/pipegen/export.sha256"

DRY_RUN=false
ALLOW_NO_ENGINE=false
TARGET_DIR="${DEFAULT_TARGET_DIR}"
SRC_DIR=""
VERSION_TAG=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --allow-no-engine)
            ALLOW_NO_ENGINE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--target-dir <dir>] [--allow-no-engine] <src_dir> [version_tag]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Preview actions and show ledger diff without modifying disk"
            echo "  --target-dir <dir>  Override target directory (default: pipegen/export)"
            echo "  --allow-no-engine   Bypass engine presence check (rehearsal only)"
            exit 0
            ;;
        *)
            if [[ -z "${SRC_DIR}" ]]; then
                SRC_DIR="$1"
            elif [[ -z "${VERSION_TAG}" ]]; then
                VERSION_TAG="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "${SRC_DIR}" ]]; then
    echo "ERROR: Source export directory argument is required." >&2
    echo "Usage: $0 [--dry-run] [--target-dir <dir>] <src_dir> [version_tag]" >&2
    exit 1
fi

if [[ ! -d "${SRC_DIR}" ]]; then
    echo "ERROR: Source directory '${SRC_DIR}' does not exist." >&2
    exit 1
fi

SRC_DIR="$(cd "${SRC_DIR}" && pwd)"

# Version tag detection
if [[ -z "${VERSION_TAG}" ]]; then
    if [[ -f "${SRC_DIR}/config.json" ]]; then
        VERSION_TAG="$(python3 -c "import json; print(json.load(open('${SRC_DIR}/config.json')).get('pipegen_version', ''))" 2>/dev/null || true)"
    fi
    if [[ -z "${VERSION_TAG}" ]]; then
        if command -v pipegen >/dev/null 2>&1; then
            VERSION_TAG="$(pipegen --version 2>&1 || echo 'pipegen-detected')"
        else
            VERSION_TAG="pipegen-export-$(date +%Y%m%d)"
        fi
    fi
fi

echo "=================================================================="
echo " SiteSentinel: PipeGen Export Ingestion"
echo "=================================================================="
echo " Source:  ${SRC_DIR}"
echo " Target:  ${TARGET_DIR}"
echo " Version: ${VERSION_TAG}"
echo " Dry Run: ${DRY_RUN}"
echo "------------------------------------------------------------------"

# GUARD 1: Empty directory check
NON_HIDDEN_COUNT=$(find "${SRC_DIR}" -maxdepth 1 ! -name ".*" ! -name "pipegen_export" | wc -l | tr -d ' ')
if [[ "${NON_HIDDEN_COUNT}" -eq 1 ]]; then
    # find includes the directory itself, count 1 means 0 children
    echo "REFUSAL [Exit 3]: Source export directory is empty." >&2
    exit 3
fi

# GUARD 2: Fixture marker check (Rule 2: Fixture can never be copied into production export)
IS_FIXTURE=false
if [[ -f "${SRC_DIR}/FIXTURE_EXPORT_DO_NOT_SUBMIT" ]]; then
    IS_FIXTURE=true
fi

# Canonical path comparison for target dir
TARGET_REAL="$(mkdir -p "${TARGET_DIR}" && cd "${TARGET_DIR}" && pwd)"
PROD_REAL="$(mkdir -p "${DEFAULT_TARGET_DIR}" && cd "${DEFAULT_TARGET_DIR}" && pwd)"

if [[ "${IS_FIXTURE}" == "true" ]]; then
    if [[ "${TARGET_REAL}" == "${PROD_REAL}" ]]; then
        if [[ "${DRY_RUN}" != "true" ]]; then
            echo "REFUSAL [Exit 2]: Source contains 'FIXTURE_EXPORT_DO_NOT_SUBMIT' marker!" >&2
            echo "Rule 2 violation: A fixture or baseline can never be ingested into production PipeGen export directory." >&2
            exit 2
        else
            echo "[NOTICE] Source contains 'FIXTURE_EXPORT_DO_NOT_SUBMIT' marker."
            echo "[NOTICE] DRY-RUN active: Simulating ingestion without modifying production files."
        fi
    else
        echo "[INFO] Ingesting fixture into non-production rehearsal target: ${TARGET_DIR}"
    fi
fi

# GUARD 3: Engine/plan existence check
ENGINE_COUNT=$(find "${SRC_DIR}" -type f \( -name "*.engine" -o -name "*.plan" -o -name "*.trt" \) | wc -l | tr -d ' ')
if [[ "${ENGINE_COUNT}" -eq 0 && "${ALLOW_NO_ENGINE}" != "true" ]]; then
    if [[ "${DRY_RUN}" != "true" ]]; then
        echo "REFUSAL [Exit 4]: Source export directory contains no TensorRT engine or plan files (*.engine, *.plan, *.trt)." >&2
        echo "PipeGen Stage 5 deliverables must contain compiled engines before ingestion." >&2
        exit 4
    else
        echo "[WARNING] No .engine or .plan files found (permitted under --dry-run rehearsal)."
    fi
fi

# Summary of changes
echo ""
echo "Files to ingest:"
find "${SRC_DIR}" -type f ! -name ".*" -exec ls -lh {} + | awk '{print "  " $9 " (" $5 ")"}'

if [[ "${DRY_RUN}" == "true" ]]; then
    echo ""
    echo "[DRY RUN] Ingestion rehearsal completed. No changes written to disk."
    echo ""
    echo "Proposed Ledger Claims Update:"
    echo "  - Claim ID: PIPEGEN-EXPORT"
    echo "    Status:   MEASURED"
    echo "    Value:    ${VERSION_TAG}"
    echo "    Target:   pipegen/export.sha256"
else
    # Copy files
    mkdir -p "${TARGET_DIR}"
    cp -r "${SRC_DIR}"/* "${TARGET_DIR}/"

    # Write version metadata
    cat <<EOF > "${TARGET_DIR}/version.json"
{
  "version": "${VERSION_TAG}",
  "ingested_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source_directory": "${SRC_DIR}"
}
EOF

    # Calculate SHA-256 for all non-manifest files inside target dir
    echo "Calculating SHA-256 manifest..."
    MANIFEST_FILE="${TARGET_DIR}/.manifest.sha256"
    rm -f "${MANIFEST_FILE}"

    cd "${TARGET_DIR}"
    find . -type f ! -name ".manifest.sha256" ! -name ".gitkeep" -print0 | sort -z | while IFS= read -r -d '' file; do
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "${file}" >> "${MANIFEST_FILE}"
        elif command -v shasum >/dev/null 2>&1; then
            shasum -a 256 "${file}" >> "${MANIFEST_FILE}"
        fi
    done

    # Write export.sha256 covering the manifest
    TARGET_EXPORT_SHA="${TARGET_DIR}/../export.sha256"
    if [[ "${TARGET_REAL}" == "${PROD_REAL}" ]]; then
        TARGET_EXPORT_SHA="${EXPORT_SHA_FILE}"
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${MANIFEST_FILE}" | awk '{print $1}' > "${TARGET_EXPORT_SHA}"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "${MANIFEST_FILE}" | awk '{print $1}' > "${TARGET_EXPORT_SHA}"
    fi

    echo "Manifest written: ${MANIFEST_FILE}"
    echo "Export root SHA:  $(cat "${TARGET_EXPORT_SHA}")"

    # Smoke test adapter
    SAMPLE_CANDIDATE=""
    if [[ -f "${TARGET_DIR}/sample_detection.json" ]]; then
        SAMPLE_CANDIDATE="${TARGET_DIR}/sample_detection.json"
    fi

    if [[ -n "${SAMPLE_CANDIDATE}" ]]; then
        PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
        if [[ ! -x "${PYTHON_BIN}" ]]; then
            PYTHON_BIN="python3"
        fi
        echo "Testing PipeGen adapter against sample detection payload..."
        "${PYTHON_BIN}" -c "
import sys
from pathlib import Path
sys.path.insert(0, '${REPO_ROOT}/src')
from sentinel.adapters.pipegen import PipeGenAdapter

adapter = PipeGenAdapter()
sample_path = Path('${SAMPLE_CANDIDATE}')
meta = adapter.parse_payload(sample_path.read_text(encoding='utf-8'))
print(f'Adapter smoke test: frame {meta.frame_id} parsed successfully with {len(meta.detections)} detections.')
"
    fi
fi

# Print Promotion Checklist
echo ""
echo "=================================================================="
echo " PipeGen Export Promotion Checklist"
echo "=================================================================="
echo "The following ledger claims can be verified and promoted on hardware day:"
echo ""
echo " 1. [PIPEGEN-EXPORT]"
echo "    Status: PENDING -> MEASURED"
echo "    Prerequisite: Real export placed in pipegen/export/ and pipegen/export.sha256 created."
echo "    Command: python tools/ledger.py promote PIPEGEN-EXPORT --source pipegen/export.sha256"
echo ""
echo " 2. [ENGINE-FPS-FP32]"
echo "    Status: PENDING -> MEASURED"
echo "    Prerequisite: evidence/pipegen/speed_report_fp32.txt from real GPU profiling run."
echo "    Command: python tools/ledger.py promote ENGINE-FPS-FP32 --source evidence/pipegen/speed_report_fp32.txt --gpu <GPU_NAME>"
echo ""
echo " 3. [ENGINE-FPS-FP16]"
echo "    Status: PENDING -> MEASURED"
echo "    Prerequisite: evidence/pipegen/speed_report_fp16.txt from real GPU profiling run."
echo "    Command: python tools/ledger.py promote ENGINE-FPS-FP16 --source evidence/pipegen/speed_report_fp16.txt --gpu <GPU_NAME>"
echo ""
echo " 4. [ENGINE-FPS-INT8]"
echo "    Status: PENDING -> MEASURED"
echo "    Prerequisite: evidence/pipegen/speed_report_int8.txt from real GPU profiling run."
echo "    Command: python tools/ledger.py promote ENGINE-FPS-INT8 --source evidence/pipegen/speed_report_int8.txt --gpu <GPU_NAME>"
echo ""
echo " 5. [HARDWARE-PLATFORM]"
echo "    Status: PENDING -> MEASURED"
echo "    Prerequisite: evidence/hardware_info.json generated by scripts/verify_hardware.sh."
echo "    Command: python tools/ledger.py promote HARDWARE-PLATFORM --source evidence/hardware_info.json --gpu <GPU_NAME>"
echo "=================================================================="
