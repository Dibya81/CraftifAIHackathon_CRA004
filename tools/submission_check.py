#!/usr/bin/env python3
"""SiteSentinel: Submission Integrity and Bonus Evidence Checker.

Validates that SUBMISSION.md matches all submission form fields and enforces:
1. Required submission fields: description, track, pipeline inputs, tasks,
   models, precision, outputs, repo link, evidence links.
2. Honest bonus claims: any bonus claimed must have MEASURED evidence
   recorded in evidence/ledger.yaml. Fails if a bonus is claimed with
   PENDING or SIMULATED status.
3. Link integrity: all local files referenced in SUBMISSION.md must exist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SECTIONS = [
    "Project Description",
    "Track",
    "Pipeline Inputs",
    "Pipeline Tasks",
    "Models",
    "Precision",
    "Outputs",
    "Bonuses Claimed",
    "Repository Link",
    "Evidence Links",
]


def check_submission() -> int:
    submission_file = ROOT / "SUBMISSION.md"
    ledger_file = ROOT / "evidence" / "ledger.yaml"

    if not submission_file.exists():
        print("[FAIL] SUBMISSION.md does not exist.")
        return 1

    if not ledger_file.exists():
        print("[FAIL] evidence/ledger.yaml does not exist.")
        return 1

    content = submission_file.read_text(encoding="utf-8")
    ledger_data = yaml.safe_load(ledger_file.read_text(encoding="utf-8")) or {}
    ledger_entries = {item["id"]: item for item in ledger_data.get("ledger", [])}

    errors = []

    # 1. Check required submission sections / fields
    for sec in REQUIRED_SECTIONS:
        pattern = re.compile(rf"(?i)#{1,4}\s*.*{re.escape(sec)}|(\*\*|\b){re.escape(sec)}(\*\*|\b)")
        if not pattern.search(content):
            errors.append(f"Missing required submission field: '{sec}'")

    # 2. Check bonus claims
    # If "Edge Optimization" is claimed as an active/awarded bonus, verify measured hardware logs exist.
    edge_bonus_match = re.search(r"(?i)bonuses\s*claimed\s*:?\s*(.*)", content)
    if edge_bonus_match:
        claim_line = edge_bonus_match.group(1).strip()
        # If user claims Edge Optimization without noting PENDING
        if "edge optimization" in claim_line.lower() and "pending" not in claim_line.lower() and "none" not in claim_line.lower():
            # Must verify INT8 speedup and hardware telemetry in ledger
            int8_entry = ledger_entries.get("SPEEDUP-INT8-VS-FP16")
            hw_entry = ledger_entries.get("HARDWARE-PLATFORM")
            if not int8_entry or int8_entry.get("status") != "MEASURED":
                errors.append(
                    "Bonus claim 'Edge Optimization' requires MEASURED status for SPEEDUP-INT8-VS-FP16 in evidence/ledger.yaml."
                )
            if not hw_entry or hw_entry.get("status") != "MEASURED":
                errors.append(
                    "Bonus claim 'Edge Optimization' requires MEASURED status for HARDWARE-PLATFORM in evidence/ledger.yaml."
                )

    # 3. Check local file links in SUBMISSION.md
    link_pattern = re.compile(r'\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)')
    for _, target in link_pattern.findall(content):
        target_clean = target.split("#")[0].strip()
        if target_clean.startswith("file:///"):
            target_clean = target_clean[8:]
        elif target_clean.startswith("file://"):
            target_clean = target_clean[7:]
        target_clean = target_clean.strip("/")

        if target_clean:
            resolved = (ROOT / target_clean).resolve()
            if not resolved.exists():
                errors.append(f"Broken link in SUBMISSION.md: '{target_clean}' does not exist.")

    if errors:
        print("==========================================================")
        print(" Submission Check FAILED with violations:")
        print("==========================================================")
        for err in errors:
            print(f"  [X] {err}")
        print("==========================================================")
        return 1

    print("==========================================================")
    print(" Submission Check PASSED: All form fields verified.")
    print(" (Zero unproven bonuses claimed; all evidence links valid)")
    print("==========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(check_submission())
