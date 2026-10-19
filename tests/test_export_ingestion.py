"""Unit and integration tests for PipeGen export ingestion rehearsal and ledger promotion."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.make_fixture_export import build_fixture_export


def test_make_fixture_export(tmp_path: Path):
    export_dir = tmp_path / "fake_export"
    build_fixture_export(export_dir, with_engine=False, with_marker=True)

    assert (export_dir / "FIXTURE_EXPORT_DO_NOT_SUBMIT").exists()
    assert (export_dir / "run.sh").exists()
    assert (export_dir / "config.json").exists()
    assert (export_dir / "sample_detection.json").exists()
    assert not list(export_dir.glob("*.engine"))


def test_ingest_refuses_fixture(tmp_path: Path):
    fixture_dir = tmp_path / "fixture_dir"
    build_fixture_export(fixture_dir, with_engine=True, with_marker=True)

    script_path = Path("scripts/ingest_pipegen_export.sh").resolve()
    proc = subprocess.run(
        [str(script_path), str(fixture_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "FIXTURE_EXPORT_DO_NOT_SUBMIT" in proc.stderr or "Rule 2 violation" in proc.stderr


def test_ingest_fixture_dry_run_succeeds(tmp_path: Path):
    fixture_dir = tmp_path / "fixture_dir"
    build_fixture_export(fixture_dir, with_engine=False, with_marker=True)

    script_path = Path("scripts/ingest_pipegen_export.sh").resolve()
    proc = subprocess.run(
        [str(script_path), "--dry-run", str(fixture_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "[DRY RUN]" in proc.stdout
    assert "PipeGen Export Promotion Checklist" in proc.stdout


def test_ingest_refuses_empty_dir(tmp_path: Path):
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    script_path = Path("scripts/ingest_pipegen_export.sh").resolve()
    proc = subprocess.run(
        [str(script_path), str(empty_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3
    assert "empty" in proc.stderr


def test_ingest_refuses_missing_engine(tmp_path: Path):
    no_eng_dir = tmp_path / "no_engine_dir"
    no_eng_dir.mkdir()
    (no_eng_dir / "run.sh").write_text("#!/bin/bash\necho ok", encoding="utf-8")
    (no_eng_dir / "config.json").write_text("{}", encoding="utf-8")

    script_path = Path("scripts/ingest_pipegen_export.sh").resolve()
    proc = subprocess.run(
        [str(script_path), str(no_eng_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 4
    assert "no TensorRT engine or plan files" in proc.stderr


def test_ingest_happy_path_in_temp_dir(tmp_path: Path):
    src_dir = tmp_path / "source_export"
    target_dir = tmp_path / "target_rehearsal"

    # Build fixture without marker (for test target only) but with engine stub
    build_fixture_export(src_dir, with_engine=True, with_marker=False)

    script_path = Path("scripts/ingest_pipegen_export.sh").resolve()
    proc = subprocess.run(
        [
            str(script_path),
            "--target-dir",
            str(target_dir),
            str(src_dir),
            "pipegen-v2.1.0-test",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert (target_dir / "version.json").exists()
    assert (target_dir / ".manifest.sha256").exists()
    assert (target_dir / "model.engine").exists()
    assert "Adapter smoke test: frame 1 parsed successfully" in proc.stdout
    assert "PipeGen Export Promotion Checklist" in proc.stdout


def test_ledger_promote_missing_file_refused():
    proc = subprocess.run(
        [
            sys.executable,
            "tools/ledger.py",
            "promote",
            "PIPEGEN-EXPORT",
            "--source",
            "nonexistent/file.sha256",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "does not exist on disk" in proc.stderr


def test_ledger_promote_hardware_without_gpu_refused():
    proc = subprocess.run(
        [sys.executable, "tools/ledger.py", "promote", "ENGINE-FPS-FP32", "--source", "README.md"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert (
        "Hardware claim cannot be promoted to MEASURED without real hardware named in environment.gpu"
        in proc.stderr
    )


def test_ledger_promote_fixture_refused():
    proc = subprocess.run(
        [
            sys.executable,
            "tools/ledger.py",
            "promote",
            "PIPEGEN-EXPORT",
            "--source",
            "tests/fixtures/pipegen_sample.json",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "is labelled as a fixture or simulated file" in proc.stderr


def test_ledger_promote_dry_run():
    proc = subprocess.run(
        [
            sys.executable,
            "tools/ledger.py",
            "promote",
            "PIPEGEN-EXPORT",
            "--source",
            "README.md",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "[DRY RUN] Would promote [PIPEGEN-EXPORT]" in proc.stdout
