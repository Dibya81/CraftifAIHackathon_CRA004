#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: PipeGen Export Ingestion Tool
# Ingests raw PipeGen export deliverables, verifies integrity, runs adapter, and updates ledger.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${REPO_ROOT}/pipegen/export"
EXPORT_SHA_FILE="${REPO_ROOT}/pipegen/export.sha256"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <path_to_pipegen_export_dir> [version_tag]"
    echo ""
    echo "Copies PipeGen stage 5 artifacts into pipegen/export/, calculates SHA-256"
    echo "hashes, writes pipegen/export.sha256, verifies adapter parsing, and updates ledger."
    exit 1
fi

SRC_DIR="$1"
VERSION_TAG="${2:-}"

if [[ -z "${VERSION_TAG}" ]]; then
    if command -v pipegen >/dev/null 2>&1; then
        VERSION_TAG="$(pipegen --version 2>&1 || echo 'pipegen-detected')"
    else
        VERSION_TAG="external-export-$(date +%Y%m%d)"
    fi
fi

if [[ ! -d "${SRC_DIR}" ]]; then
    echo "ERROR: Source directory '${SRC_DIR}' does not exist." >&2
    exit 1
fi

echo "Ingesting PipeGen export from: ${SRC_DIR}"
mkdir -p "${TARGET_DIR}"

# Copy all files from source directory into target export dir
cp -r "${SRC_DIR}"/* "${TARGET_DIR}/"

# Write version metadata
cat <<EOF > "${TARGET_DIR}/version.json"
{
  "version": "${VERSION_TAG}",
  "ingested_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source_directory": "${SRC_DIR}"
}
EOF

# Calculate SHA-256 for all non-manifest files inside export dir
echo "Calculating SHA-256 manifest..."
MANIFEST_FILE="${TARGET_DIR}/.manifest.sha256"
rm -f "${MANIFEST_FILE}"

cd "${TARGET_DIR}"
find . -type f ! -name ".manifest.sha256" ! -name ".gitkeep" -print0 | sort -z | while IFS= read -r -d '' file; do
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${file}" >> "${MANIFEST_FILE}"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "${file}" >> "${MANIFEST_FILE}"
    else
        echo "ERROR: Neither sha256sum nor shasum is available." >&2
        exit 1
    fi
done

# Write pipegen/export.sha256 covering the manifest
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${MANIFEST_FILE}" | awk '{print $1}' > "${EXPORT_SHA_FILE}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${MANIFEST_FILE}" | awk '{print $1}' > "${EXPORT_SHA_FILE}"
fi

echo "Manifest written to: ${MANIFEST_FILE}"
echo "Export root SHA written to: ${EXPORT_SHA_FILE} ($(cat "${EXPORT_SHA_FILE}"))"

# Run adapter verification against captured sample
echo "Verifying PipeGen adapter against captured sample..."
SAMPLE_CANDIDATE=""
if [[ -f "${TARGET_DIR}/sample_detection.json" ]]; then
    SAMPLE_CANDIDATE="${TARGET_DIR}/sample_detection.json"
elif [[ -f "${REPO_ROOT}/tests/fixtures/pipegen_sample.json" ]]; then
    SAMPLE_CANDIDATE="${REPO_ROOT}/tests/fixtures/pipegen_sample.json"
fi

if [[ -n "${SAMPLE_CANDIDATE}" ]]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    if [[ ! -x "${PYTHON_BIN}" ]]; then
        PYTHON_BIN="python3"
    fi
    "${PYTHON_BIN}" -c "
import sys
from pathlib import Path
from sentinel.adapters.pipegen import PipeGenAdapter

adapter = PipeGenAdapter()
sample_path = Path('${SAMPLE_CANDIDATE}')
meta = adapter.parse_payload(sample_path.read_text(encoding='utf-8'))
print(f'Adapter verified: parsed frame {meta.frame_id} with {len(meta.detections)} detections.')
"
fi

# Update ledger entry for pipegen_export
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi
"${PYTHON_BIN}" -c "
import yaml
from pathlib import Path
ledger_path = Path('${REPO_ROOT}/evidence/ledger.yaml')
if ledger_path.exists():
    with open(ledger_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    sha_path = Path('${EXPORT_SHA_FILE}')
    export_sha = sha_path.read_text().strip() if sha_path.exists() else 'PENDING'
    for item in data.get('claims', []):
        if item.get('id') == 'pipegen_export':
            item['status'] = 'MEASURED'
            item['value'] = '${VERSION_TAG}'
            item['sha256'] = export_sha
            item['notes'] = 'Ingested via scripts/ingest_pipegen_export.sh'
    with open(ledger_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False)
    print('Updated evidence/ledger.yaml claim: pipegen_export')
"

echo "Ingestion complete."
