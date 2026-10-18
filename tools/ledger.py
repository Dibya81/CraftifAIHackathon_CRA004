"""SiteSentinel Claims Ledger Tool.

Usage:
  python tools/ledger.py verify          # Recompute hashes, fail on any violation
  python tools/ledger.py summary         # Print counts of MEASURED / SIMULATED / PENDING
  python tools/ledger.py list [STATUS]   # List entries, optionally filtered by status
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "evidence" / "ledger.yaml"

VALID_STATUSES = {"MEASURED", "SIMULATED", "PENDING"}


def verify_ledger(path: Path | str = LEDGER_PATH) -> Tuple[int, List[str]]:
    """Programmatic entry point to verify ledger.yaml. Returns (violations_count, error_messages)."""
    p = Path(path)
    if not p.exists():
        return 1, [f"Ledger file not found: {p}"]
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries", [])
    violations = verify(entries)
    return violations, []


def load_ledger() -> Dict[str, Any]:
    if not LEDGER_PATH.exists():
        print(f"ERROR: Ledger not found at {LEDGER_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(entries: List[Dict[str, Any]]) -> int:
    """Return number of violations found."""
    violations = 0

    for entry in entries:
        eid = entry.get("id", "<no-id>")
        status = entry.get("status", "")
        value = entry.get("value")
        source_file = entry.get("source_file")
        sha256 = entry.get("sha256")
        env = entry.get("environment", {}) or {}
        gpu = env.get("gpu", "")

        # Rule 1: status must be valid
        if status not in VALID_STATUSES:
            print(
                f"FAIL [{eid}]: invalid status '{status}' — must be MEASURED, SIMULATED, or PENDING"
            )
            violations += 1
            continue

        # Rule 2: if there's a value, there must be source_file + sha256 (unless PENDING)
        if value is not None and status != "PENDING":
            if not source_file:
                print(f"FAIL [{eid}]: has value={value!r} but source_file is null")
                violations += 1
            if not sha256 or sha256.startswith("PENDING"):
                print(f"FAIL [{eid}]: has value={value!r} but sha256 is null/PENDING")
                violations += 1

        # Rule 3: MEASURED entries with gpu=none must not claim hardware metrics
        if status == "MEASURED" and str(gpu).lower() in {"none", ""}:
            hardware_keywords = {
                "fps",
                "fps/w",
                "vram",
                "watt",
                "power",
                "tensorrt",
                "int8",
                "fp16",
            }
            claim = entry.get("claim", "").lower()
            if any(kw in claim for kw in hardware_keywords):
                print(
                    f"FAIL [{eid}]: status=MEASURED but environment.gpu=none "
                    f"yet claim mentions hardware metric: '{entry.get('claim')}'"
                )
                violations += 1

        # Rule 4: if source_file is set, verify it exists and hash matches
        if (
            source_file
            and not source_file.startswith("PENDING")
            and sha256
            and not sha256.startswith("PENDING")
        ):
            src_path = REPO_ROOT / source_file
            if src_path.is_dir():
                pass  # Directories (like tests/) can't be hashed directly
            elif not src_path.exists():
                print(f"FAIL [{eid}]: source_file '{source_file}' does not exist on disk")
                violations += 1
            else:
                actual = sha256_file(src_path)
                if actual != sha256:
                    print(
                        f"FAIL [{eid}]: sha256 mismatch for '{source_file}'\n"
                        f"  stored:   {sha256}\n"
                        f"  computed: {actual}"
                    )
                    violations += 1
                else:
                    pass  # Hash OK

    return violations


def cmd_verify() -> None:
    data = load_ledger()
    entries = data.get("entries", [])
    print(f"Verifying {len(entries)} ledger entries...")
    violations = verify(entries)
    if violations == 0:
        print(f"OK — {len(entries)} entries verified, 0 violations.")
    else:
        print(f"\nFAIL — {violations} violation(s) found. Fix them before judging.")
        sys.exit(1)


def cmd_summary() -> None:
    data = load_ledger()
    entries = data.get("entries", [])
    counts = {"MEASURED": 0, "SIMULATED": 0, "PENDING": 0, "UNKNOWN": 0}
    for e in entries:
        s = e.get("status", "UNKNOWN")
        counts[s] = counts.get(s, 0) + 1
    print(f"Ledger summary ({len(entries)} total entries):")
    print(f"  MEASURED:  {counts['MEASURED']}")
    print(f"  SIMULATED: {counts['SIMULATED']}")
    print(f"  PENDING:   {counts['PENDING']}")
    if counts.get("UNKNOWN", 0):
        print(f"  UNKNOWN:   {counts['UNKNOWN']}")


def cmd_list(filter_status: Optional[str] = None) -> None:
    data = load_ledger()
    entries = data.get("entries", [])
    for e in entries:
        status = e.get("status", "?")
        if filter_status and status != filter_status.upper():
            continue
        value = e.get("value")
        val_str = str(value) if value is not None else "(null)"
        print(
            f"[{status:9s}] {e.get('id', '?'):30s}  value={val_str:15s}  {e.get('claim', '')[:60]}"
        )


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "verify":
        cmd_verify()
    elif args[0] == "summary":
        cmd_summary()
    elif args[0] == "list":
        cmd_list(args[1] if len(args) > 1 else None)
    else:
        print(f"Unknown command: {args[0]}. Use: verify | summary | list [STATUS]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
