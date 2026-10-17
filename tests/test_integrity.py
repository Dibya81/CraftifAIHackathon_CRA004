"""Repository integrity and immutability tests (TC-04, TC-05, TC-30)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from sentinel.config import load_sentinel_config


@pytest.mark.tc("TC-04")
def test_tc04_pipegen_export_hash_manifest():
    """TC-04: Verify SHA-256 hash manifest of pipegen/export/ to prove untouched export."""
    export_dir = Path("pipegen/export")
    assert export_dir.exists(), "pipegen/export directory must exist."

    manifest_file = export_dir / ".manifest.sha256"
    assert manifest_file.exists(), ".manifest.sha256 file must exist in pipegen/export."

    manifest_lines = manifest_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest_lines) > 0, "Manifest file must not be empty."

    for line in manifest_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected_hash, rel_path = line.split(maxsplit=1)
        rel_path = rel_path.strip()
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]
        target_file = export_dir / rel_path
        assert target_file.exists(), f"Manifest file entry '{rel_path}' does not exist on disk."

        hasher = hashlib.sha256()
        hasher.update(target_file.read_bytes())
        actual_hash = hasher.hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {rel_path}: {actual_hash} != {expected_hash}"
        )


@pytest.mark.tc("TC-05")
def test_tc05_static_code_scan_prohibited_pipegen_writes():
    """TC-05: Scan all source files to assert zero write/open-write calls targeting pipegen/export."""
    repo_root = Path(".")
    prohibited_patterns = [
        re.compile(r'open\s*\([^)]*pipegen/export[^)]*["\'][wa\+]["\']'),
        re.compile(r"Path\s*\([^)]*pipegen/export[^)]*\)\.(write_text|write_bytes|mkdir)"),
        re.compile(r"shutil\.(copy|move|rmtree)\s*\([^)]*pipegen/export"),
    ]

    scanned_extensions = {".py", ".sh", ".bash"}
    violations = []

    for path in repo_root.rglob("*"):
        if path.is_file() and path.suffix in scanned_extensions:
            # Skip git, venv, and the test itself
            parts = path.parts
            if any(p.startswith(".") or p in {"venv", ".venv", "tests"} for p in parts):
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in prohibited_patterns:
                    matches = pattern.findall(content)
                    if matches:
                        violations.append(f"{path}: Matched write pattern {pattern.pattern}")
            except Exception:
                continue

    assert len(violations) == 0, f"Prohibited write references found in code: {violations}"


@pytest.mark.tc("TC-30")
def test_tc30_mqtt_topic_contract_parity():
    """TC-30: Assert config topic names match those documented in docs/ARCHITECTURE.md."""
    config_file = Path("config/sentinel.yaml")
    assert config_file.exists(), "config/sentinel.yaml must exist."

    cfg = load_sentinel_config(config_file)
    arch_doc = Path("docs/ARCHITECTURE.md")
    assert arch_doc.exists(), "docs/ARCHITECTURE.md must exist."

    arch_text = arch_doc.read_text(encoding="utf-8")

    # Verify that each configured topic is documented in ARCHITECTURE.md
    assert cfg.mqtt.detections_topic in arch_text, (
        f"detections_topic '{cfg.mqtt.detections_topic}' not documented in docs/ARCHITECTURE.md"
    )
    assert cfg.mqtt.incidents_topic in arch_text, (
        f"incidents_topic '{cfg.mqtt.incidents_topic}' not documented in docs/ARCHITECTURE.md"
    )
    assert cfg.mqtt.health_topic in arch_text, (
        f"health_topic '{cfg.mqtt.health_topic}' not documented in docs/ARCHITECTURE.md"
    )
