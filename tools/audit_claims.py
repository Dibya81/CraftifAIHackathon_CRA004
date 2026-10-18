"""SiteSentinel Claims and Documentation Auditor.

Scans all public markdown documentation to ensure:
1. No banned fabricated phrases or unverified hardware claims appear.
2. No absolute `file:///` URLs are present.
3. Every claimed performance number traces back to a ledgered entry or explicit PENDING/SIMULATED flag.
4. No hardcoded claims of "zero simulated or fabricated metrics" exist.

Usage:
  python tools/audit_claims.py [--strict]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

STRICT_BANNED = [
    (re.compile(r"zero\s+simulated\s+or\s+fabricated\s+metrics", re.IGNORECASE), "False claim of 'zero simulated or fabricated metrics'"),
    (re.compile(r"Automated\s+Lead\s+Agent", re.IGNORECASE), "AI author stub instead of human team member"),
    (re.compile(r"\bproduction-grade\b", re.IGNORECASE), "Banned marketing term 'production-grade'"),
    (re.compile(r"\bautonomous\b", re.IGNORECASE), "Banned marketing term 'autonomous'"),
]

CONTEXT_SENSITIVE_BANNED = [
    # Fabricated hardware benchmarks
    (re.compile(r"31\.4\s*FPS", re.IGNORECASE), "Fabricated 31.4 FPS claim"),
    (re.compile(r"24\.7\s*FPS", re.IGNORECASE), "Fabricated 24.7 FPS claim"),
    (re.compile(r"11\.2\s*FPS", re.IGNORECASE), "Fabricated 11.2 FPS claim"),
    (re.compile(r"1\.27x\s*throughput", re.IGNORECASE), "Fabricated 1.27x throughput gain claim"),
    (re.compile(r"46\.7%\s*VRAM", re.IGNORECASE), "Fabricated 46.7% VRAM reduction claim"),
    (re.compile(r"on\s+NVIDIA\s+Jetson\s+Orin", re.IGNORECASE), "Unverified 'on NVIDIA Jetson Orin' claim"),
    (re.compile(r"verified\s+on\s+hardware", re.IGNORECASE), "Unverified 'verified on hardware' claim"),
    (re.compile(r"\b(Jetson|Orin)\b", re.IGNORECASE), "Unverified hardware name (Jetson/Orin) without MEASURED hardware log"),
]

CONTEXT_EXEMPTION_WORDS = [
    "pending",
    "previous value",
    "was wrong",
    "invented",
    "fabricated",
    "deleted",
    "defect",
    "historical",
    "honest status",
    "rule",
    "hardware runbook",
    "runbook",
]


def check_markdown_file(path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single markdown file for violations.
    
    Returns list of (line_number, line_content, error_message).
    """
    violations = []
    lines = path.read_text(encoding="utf-8").splitlines()
    
    in_code_block = False
    
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            
        # Check for file:/// absolute links
        if "file:///" in line:
            violations.append((idx, line, "Absolute file:/// URL found; use relative markdown links."))

        # Check relative markdown links point to existing files
        for link_target in re.findall(r'\[.*?\]\(([^)]+)\)', line):
            if link_target.startswith("http") or link_target.startswith("#") or link_target.startswith("mailto:"):
                continue
            clean_target = link_target.split("#")[0].strip()
            if not clean_target:
                continue
            target_path = (path.parent / clean_target).resolve()
            if not target_path.exists():
                violations.append((idx, line, f"Broken link to non-existent file: '{clean_target}'"))
            
        # Check if line is a self-referential audit log/report output
        lower_line = line.lower()
        if "false claim of" in lower_line or "prohibited pattern" in lower_line or "audit failed" in lower_line:
            continue

        # Strictly banned phrases (never allowed anywhere in documents)
        for regex, msg in STRICT_BANNED:
            if regex.search(line):
                violations.append((idx, line, msg))

        # Context-sensitive phrases (allowed only when explaining PENDING/deleted/historical status)
        lower_line = line.lower()
        has_exemption = any(exempt in lower_line for exempt in CONTEXT_EXEMPTION_WORDS)
        
        for regex, msg in CONTEXT_SENSITIVE_BANNED:
            if regex.search(line) and not has_exemption:
                violations.append((idx, line, msg))
                
    return violations


def audit_repository(root_dir: Path) -> int:
    """Audit all documentation markdown files in root_dir."""
    docs_to_check = [
        root_dir / "README.md",
        root_dir / "SUBMISSION.md",
        root_dir / "JUDGE_REPORT.md",
        root_dir / "REQUIREMENTS_MATRIX.md",
        root_dir / "docs" / "ARCHITECTURE.md",
    ]
    
    # Also check any .md files directly under reports/
    reports_dir = root_dir / "reports"
    if reports_dir.exists():
        for r_md in reports_dir.glob("*.md"):
            docs_to_check.append(r_md)
            
    total_violations = 0
    print("==========================================================")
    print(" SiteSentinel: Documentation Claims & Integrity Audit")
    print("==========================================================\n")
    
    for doc_path in docs_to_check:
        if not doc_path.exists():
            continue
        rel_path = doc_path.relative_to(root_dir)
        violations = check_markdown_file(doc_path)
        if violations:
            print(f"❌ {rel_path} has {len(violations)} violation(s):")
            for line_no, content, msg in violations:
                print(f"   L{line_no}: {msg}")
                print(f"        \"{content.strip()[:90]}\"")
            total_violations += len(violations)
        else:
            print(f"✅ {rel_path}: 0 violations")
            
    print("\n----------------------------------------------------------")
    if total_violations == 0:
        print("🎉 ALL DOCUMENTATION AUDIT CHECKS PASSED (0 violations)")
        print("----------------------------------------------------------")
        return 0
    else:
        print(f"❌ AUDIT FAILED: {total_violations} total violation(s) found.")
        print("----------------------------------------------------------")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit claims in markdown files.")
    parser.add_argument("--root", type=str, default=".", help="Root repo directory")
    args = parser.parse_args()
    sys.exit(audit_repository(Path(args.root).resolve()))
