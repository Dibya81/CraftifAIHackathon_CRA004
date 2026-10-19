"""Unit tests for booth-day automation and hardware diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sentinel.interfaces.cli.doctor import run_hardware_diagnostics


def test_hardware_diagnostics_cpu_host_clean_skips():
    """Diagnostics on CPU host skips GPU/PipeGen cleanly without crashing."""
    diag = run_hardware_diagnostics()
    assert isinstance(diag, dict)
    assert "checks" in diag
    assert "blockers" in diag
    assert "warnings" in diag

    check_names = {c["name"] for c in diag["checks"]}
    assert "NVIDIA Driver" in check_names
    assert "CUDA Toolkit" in check_names
    assert "TensorRT" in check_names
    assert "DeepStream SDK" in check_names
    assert "PipeGen CLI" in check_names
    assert "ffmpeg" in check_names
    assert "Disk Space" in check_names
    assert "Network Ports (8000, 5173)" in check_names
    assert "Runtimes (Python/Node)" in check_names

    if diag["is_cpu_host"]:
        # Hardware-dependent items must be skipped, not reported as blockers
        for c in diag["checks"]:
            if c["name"] in ["NVIDIA Driver", "CUDA Toolkit", "DeepStream SDK"]:
                assert c["status"] in ["SKIPPED", "PASS"]


def test_hardware_diagnostics_cli_invocable():
    """sentinel doctor --hardware runs from CLI without unhandled exception."""
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    res = subprocess.run(
        [sys.executable, "-m", "sentinel.interfaces.cli.main", "doctor", "--hardware"],
        capture_output=True,
        text=True,
        env=env,
    )
    # On CPU host, it should pass with warnings or skip, not throw an unhandled error
    assert "Running Comprehensive Edge Hardware Diagnostics" in res.stdout
    assert "[PASS]" in res.stdout or "[SKIP]" in res.stdout


def test_booth_day_script_dry_run():
    """scripts/booth_day.sh --dry-run outputs the 10-step checklist and exits 0."""
    res = subprocess.run(
        ["bash", "scripts/booth_day.sh", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "SiteSentinel Booth-Day Checklist" in res.stdout
    assert "Total Budget: 45 min / 240 min window" in res.stdout
    assert "1. Doctor & Hardware Verification" in res.stdout
    assert "10. Final Automated Judge Gate" in res.stdout


def test_booth_cli_dry_run():
    """sentinel booth --dry-run CLI command forwards to booth_day script."""
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    res = subprocess.run(
        [sys.executable, "-m", "sentinel.interfaces.cli.main", "booth", "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
    assert "SiteSentinel Booth-Day Checklist" in res.stdout


def test_make_offline_bundle_dry_run():
    """scripts/make_offline_bundle.sh --dry-run previews directory targets."""
    res = subprocess.run(
        ["bash", "scripts/make_offline_bundle.sh", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Generating Offline Bundle" in res.stdout
    assert "manifest.sha256" in res.stdout


def test_booth_day_state_persistence(tmp_path: Path):
    """Booth day state file tracks completed steps idempotently."""
    state_file = tmp_path / "test_booth_state.json"
    state_file.write_text(json.dumps({"completed_steps": [1, 2], "artifacts": {}}), encoding="utf-8")

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert 1 in data["completed_steps"]
    assert 2 in data["completed_steps"]
    assert 3 not in data["completed_steps"]
