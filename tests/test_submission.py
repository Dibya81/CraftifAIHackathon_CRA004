from pathlib import Path

import pytest

from tools.make_submission import SubmissionCollector, main


@pytest.mark.tc("TC-01")
def test_audit_deliverables_detects_existing_assets():
    collector = SubmissionCollector(Path("."))
    audits = collector.audit_deliverables()

    names = {a.name: a for a in audits}

    # Core software assets must exist
    assert "Architecture Specification" in names
    assert names["Architecture Specification"].exists is True
    assert names["PipeGen Requirement (Stage 1)"].exists is True
    assert names["Interactive React Dashboard"].exists is True
    assert names["One-Click Demo Runner"].exists is True


def test_audit_deliverables_flags_pending_hardware_items():
    collector = SubmissionCollector(Path("."))
    audits = collector.audit_deliverables()

    hw_audits = [a for a in audits if a.is_hardware_dependent]
    assert len(hw_audits) == 4

    hw_names = {a.name for a in hw_audits}
    assert "Pipeline IR Node Graph Screenshot" in hw_names
    assert "TensorRT FP16 Speed Report (CLI)" in hw_names
    assert "TensorRT INT8 Speed Report (CLI)" in hw_names
    assert "Hardware Telemetry Log (tegrastats / nvidia-smi)" in hw_names

    for a in hw_audits:
        assert a.todo_ref is not None
        assert "Hardware step" in a.todo_ref


def test_generate_submission_markdown_contents():
    collector = SubmissionCollector(Path("."))
    content = collector.generate_submission_markdown()

    # Verify structural sections
    assert "# SiteSentinel: CraftifAI Physical AI Submission Pack" in content
    assert "Track A: PipeGen" in content
    assert "Edge Optimization" in content
    assert "## 1. Executive Summary & Safety Problem" in content
    assert "## 2. Track A: PipeGen 5-Stage Traceability" in content
    assert "## 3. System Architecture & Zero-Copy Data Flow" in content
    assert "## 4. Edge Optimization Bonus Report (FP32 vs FP16 vs INT8)" in content
    assert "## 5. Offline Evaluation & Accuracy Benchmark" in content
    assert "## 6. Privacy by Design Enforcement" in content
    assert "## 7. Live Control Room Dashboard & Spatial Zone Intelligence" in content
    assert "## 8. Submission Deliverables Checklist & Evidence Audit" in content
    assert "## 9. 5-Minute Quickstart & Verification Commands" in content
    assert "## 10. Judge Walkthrough Script (4 Minutes)" in content

    # Verify metrics rendered
    assert "Speedup" in content
    assert "100.0%" in content  # precision/recall


def test_cli_execution_check_only(monkeypatch):
    monkeypatch.setattr("sys.argv", ["make_submission.py", "--check-only"])
    code = main()
    assert code == 0


def test_cli_execution_strict_pass(monkeypatch):
    monkeypatch.setattr("sys.argv", ["make_submission.py", "--check-only", "--strict"])
    code = main()
    assert code == 0


def test_cli_strict_fails_on_missing_software(tmp_path: Path, monkeypatch):
    # Empty temporary directory lacks core software assets
    monkeypatch.setattr(
        "sys.argv",
        ["make_submission.py", "--root", str(tmp_path), "--check-only", "--strict"],
    )
    code = main()
    assert code == 1
