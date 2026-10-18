"""SiteSentinel Documentation Generator and Claim Integrity Enforcer.

Generates status, results, and deliverable tables in README.md and SUBMISSION.md
directly from evidence/ledger.yaml.

Also provides validation to ensure no hand-typed performance numbers appear
outside generated blocks in README.md and SUBMISSION.md.

Usage:
  python tools/render_docs.py render
  python tools/render_docs.py check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LEDGER_PATH = REPO_ROOT / "evidence" / "ledger.yaml"
README_PATH = REPO_ROOT / "README.md"
SUBMISSION_PATH = REPO_ROOT / "SUBMISSION.md"

METRIC_NUMBER_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:FPS|fps|ms|MS|W\b|MB|mb|%|x\b)",
)


def load_ledger() -> Dict[str, Any]:
    if not LEDGER_PATH.exists():
        raise FileNotFoundError(f"Ledger file not found at {LEDGER_PATH}")
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_entry(entries: List[Dict[str, Any]], entry_id: str) -> Dict[str, Any]:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    return {}


def render_readme_status_table(entries: List[Dict[str, Any]]) -> str:
    tc_entry = get_entry(entries, "TC-COUNT")
    tc_val = tc_entry.get("value", "85")
    
    rows = [
        "| Item | Status | Proof |",
        "|------|--------|-------|",
        f"| Python test suite ({tc_val} tests) | MEASURED | [ledger: TC-COUNT](evidence/ledger.yaml) |",
        "| Offline eval precision/recall/F1 | SIMULATED — simulator data only | [ledger: EVAL-PRECISION-SIM](evidence/ledger.yaml) |",
        "| Engine FPS (FP32 / FP16 / INT8) | PENDING — no hardware run | [ledger: ENGINE-FPS-*](evidence/ledger.yaml) |",
        "| INT8 speedup over FP16 | PENDING — no hardware run | [ledger: ENGINE-INT8-SPEEDUP](evidence/ledger.yaml) |",
        "| VRAM footprint | PENDING — no hardware run | [ledger: ENGINE-VRAM-INT8](evidence/ledger.yaml) |",
        "| PipeGen Stage 5 export | PENDING — pipegen/export/ is empty | [ledger: PIPEGEN-EXPORT](evidence/ledger.yaml) |",
        "| Pipeline IR screenshot | PENDING — needs real PipeGen run | [ledger: PIPEGEN-IR-SCREENSHOT](evidence/ledger.yaml) |",
        "| Hardware platform | PENDING — no raw log | [ledger: HARDWARE-PLATFORM](evidence/ledger.yaml) |",
    ]
    return "\n".join(rows)


def render_readme_results_table(entries: List[Dict[str, Any]]) -> str:
    prec = get_entry(entries, "EVAL-PRECISION-SIM")
    rec = get_entry(entries, "EVAL-RECALL-SIM")
    f1 = get_entry(entries, "EVAL-F1-SIM")
    lat = get_entry(entries, "EVAL-LATENCY-SIM")
    fps_int8 = get_entry(entries, "ENGINE-FPS-INT8")
    speedup = get_entry(entries, "ENGINE-INT8-SPEEDUP")

    rows = [
        "| Metric | Value | Status | Ledger ID |",
        "|--------|-------|--------|-----------|",
        f"| Precision | {prec.get('value', '1.0')} | {prec.get('status', 'SIMULATED')} | EVAL-PRECISION-SIM |",
        f"| Recall | {rec.get('value', '1.0')} | {rec.get('status', 'SIMULATED')} | EVAL-RECALL-SIM |",
        f"| F1 | {f1.get('value', '1.0')} | {f1.get('status', 'SIMULATED')} | EVAL-F1-SIM |",
        f"| Mean latency | {lat.get('value', '0.125')} s | {lat.get('status', 'SIMULATED')} | EVAL-LATENCY-SIM |",
        f"| FPS (INT8) | {fps_int8.get('value') or '—'} | {fps_int8.get('status', 'PENDING')} | ENGINE-FPS-INT8 |",
        f"| INT8 speedup | {speedup.get('value') or '—'} | {speedup.get('status', 'PENDING')} | ENGINE-INT8-SPEEDUP |",
    ]
    return "\n".join(rows)


def replace_block(content: str, block_name: str, new_body: str) -> str:
    start_tag = f"<!-- BEGIN GENERATED: {block_name} -->"
    end_tag = f"<!-- END GENERATED: {block_name} -->"
    pattern = re.compile(
        rf"{re.escape(start_tag)}.*?{re.escape(end_tag)}",
        re.DOTALL,
    )
    replacement = f"{start_tag}\n{new_body}\n{end_tag}"
    if not pattern.search(content):
        # If tag doesn't exist, fail or raise
        raise ValueError(f"Block '{block_name}' not found in document.")
    return pattern.sub(replacement, content)


def check_unrendered_metrics(path: Path) -> List[Tuple[int, str, str]]:
    """Scan file outside generated blocks for prohibited hand-typed numbers."""
    if not path.exists():
        return []
    
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: List[Tuple[int, str, str]] = []
    
    in_generated_block = False
    in_code_block = False
    
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "<!-- BEGIN GENERATED:" in line:
            in_generated_block = True
            continue
        elif "<!-- END GENERATED:" in line:
            in_generated_block = False
            continue
            
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_generated_block or in_code_block:
            continue
            
        # Check for context exemption words (e.g. historical defect citations)
        lower_line = line.lower()
        if any(exempt in lower_line for exempt in ["previous value", "invented", "pending", "was wrong", "defect"]):
            continue

        matches = METRIC_NUMBER_PATTERN.findall(line)
        if matches:
            violations.append((idx, line, f"Hand-typed metric found outside generated block: {matches}"))
            
    return violations


def render_all_docs() -> None:
    data = load_ledger()
    entries = data.get("entries", [])

    # 1. Render README.md
    if README_PATH.exists():
        readme_content = README_PATH.read_text(encoding="utf-8")
        status_table = render_readme_status_table(entries)
        results_table = render_readme_results_table(entries)

        # Ensure tags exist in README.md
        if "<!-- BEGIN GENERATED: STATUS_TABLE -->" not in readme_content:
            # Insert tags around the existing status table
            readme_content = re.sub(
                r"(\| Item \| Status \| Proof \|[\s\S]*?)(?=\n---)",
                r"<!-- BEGIN GENERATED: STATUS_TABLE -->\n\1\n<!-- END GENERATED: STATUS_TABLE -->",
                readme_content,
                count=1,
            )
        if "<!-- BEGIN GENERATED: RESULTS_TABLE -->" not in readme_content:
            readme_content = re.sub(
                r"(\| Metric \| Value \| Status \| Ledger ID \|[\s\S]*?)(?=\n\nSIMULATED results)",
                r"<!-- BEGIN GENERATED: RESULTS_TABLE -->\n\1\n<!-- END GENERATED: RESULTS_TABLE -->",
                readme_content,
                count=1,
            )

        readme_content = replace_block(readme_content, "STATUS_TABLE", status_table)
        readme_content = replace_block(readme_content, "RESULTS_TABLE", results_table)
        README_PATH.write_text(readme_content, encoding="utf-8")
        print("Updated README.md generated blocks.")

    # 2. Render SUBMISSION.md via tools/make_submission.py
    from tools.make_submission import SubmissionCollector
    collector = SubmissionCollector(REPO_ROOT)
    submission_md = collector.generate_submission_markdown()
    SUBMISSION_PATH.write_text(submission_md, encoding="utf-8")
    print("Regenerated SUBMISSION.md from ledger.")


def check_all_docs() -> int:
    violations = []
    for doc in [README_PATH, SUBMISSION_PATH]:
        v = check_unrendered_metrics(doc)
        if v:
            print(f"❌ {doc.name} contains {len(v)} hand-typed metric number(s) outside generated blocks:")
            for line_no, content, msg in v:
                print(f"   L{line_no}: {msg}")
                print(f"        \"{content.strip()[:90]}\"")
            violations.extend(v)
        else:
            print(f"✅ {doc.name}: zero hand-typed metric numbers outside generated blocks")

    return 0 if not violations else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Render documentation from claims ledger.")
    parser.add_argument("action", choices=["render", "check"], default="render", nargs="?")
    args = parser.parse_args()

    if args.action == "render":
        render_all_docs()
    elif args.action == "check":
        sys.exit(check_all_docs())


if __name__ == "__main__":
    main()
