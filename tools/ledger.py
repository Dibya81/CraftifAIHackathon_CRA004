"""SiteSentinel Claims Ledger Tool.

Usage:
  python tools/ledger.py verify          # Recompute hashes, fail on any violation
  python tools/ledger.py summary         # Print counts of MEASURED / SIMULATED / PENDING
  python tools/ledger.py list [STATUS]   # List entries, optionally filtered by status
"""

from __future__ import annotations

import argparse
import datetime
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

def cmd_promote(
    entry_id: str,
    source_file: Optional[str] = None,
    gpu: Optional[str] = None,
    value: Optional[str] = None,
    notes: Optional[str] = None,
    dry_run: bool = False,
) -> None:
    data = load_ledger()
    entries = data.get("entries", [])
    target_entry = None
    for e in entries:
        if str(e.get("id", "")).strip().upper() == entry_id.strip().upper():
            target_entry = e
            break

    if target_entry is None:
        print(f"ERROR: Entry '{entry_id}' not found in ledger.", file=sys.stderr)
        sys.exit(1)

    eid = target_entry.get("id")
    src = source_file or target_entry.get("source_file")
    if not src or str(src).startswith("PENDING"):
        print(f"REFUSAL [{eid}]: Source file is not specified. Provide --source <path>.", file=sys.stderr)
        sys.exit(1)

    src_str = str(src).strip()
    src_path = REPO_ROOT / src_str
    if not src_path.exists():
        print(f"REFUSAL [{eid}]: Source file '{src_str}' does not exist on disk.", file=sys.stderr)
        sys.exit(1)

    # Fixture guard: cannot promote if source file is a fixture or simulated file
    if any(k in src_str.lower() for k in ("fixture", "simulated", "fake")):
        print(
            f"REFUSAL [{eid}]: Source file '{src_str}' is labelled as a fixture or simulated file. "
            f"Fixtures cannot be promoted to MEASURED.",
            file=sys.stderr,
        )
        sys.exit(1)

    if src_path.is_file():
        try:
            head = src_path.read_bytes()[:1000]
            if b"FIXTURE_EXPORT_DO_NOT_SUBMIT" in head or b"THIS IS A TEST FIXTURE EXPORT" in head:
                print(
                    f"REFUSAL [{eid}]: Source file '{src_str}' contains fixture marker content. Promotion rejected.",
                    file=sys.stderr,
                )
                sys.exit(1)
        except Exception:
            pass

    # Hardware claim check
    hardware_keywords = {
        "fps",
        "fps/w",
        "vram",
        "watt",
        "power",
        "tensorrt",
        "int8",
        "fp16",
        "jetson",
        "orin",
        "gpu",
        "hardware",
    }
    claim_text = (target_entry.get("claim") or "").lower() + " " + str(eid).lower()
    is_hardware_claim = any(kw in claim_text for kw in hardware_keywords)

    current_env = target_entry.get("environment") or {}
    if not isinstance(current_env, dict):
        current_env = {}

    target_gpu = gpu or current_env.get("gpu")
    if is_hardware_claim:
        if not target_gpu or str(target_gpu).lower() in {"none", "cpu", "pending", "simulated", ""}:
            print(
                f"REFUSAL [{eid}]: Hardware claim cannot be promoted to MEASURED without real hardware named in environment.gpu. "
                f"Current gpu='{target_gpu}'. Pass --gpu '<REAL_HARDWARE_NAME>' (e.g. --gpu 'Orin Nano 8GB') when running on physical device.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Compute hash
    if src_path.is_dir():
        computed_hash = "n/a-directory"
    else:
        computed_hash = sha256_file(src_path)

    # Determine value
    target_value = value
    if target_value is None:
        if target_entry.get("value") is not None:
            target_value = target_entry.get("value")
        elif src_path.is_file() and src_path.suffix == ".sha256":
            target_value = src_path.read_text(encoding="utf-8").strip()[:64]
        elif src_path.is_file() and src_path.suffix in {".json", ".txt"}:
            target_value = f"verified-{src_path.name}"
        else:
            target_value = "verified"

    if dry_run:
        print(f"[DRY RUN] Would promote [{eid}]:")
        print("  status:      PENDING -> MEASURED")
        print(f"  source_file: {src_str}")
        print(f"  sha256:      {computed_hash}")
        print(f"  value:       {target_value}")
        if target_gpu:
            print(f"  gpu:         {target_gpu}")
        return

    # Apply changes
    target_entry["status"] = "MEASURED"
    target_entry["source_file"] = src_str
    target_entry["sha256"] = computed_hash
    target_entry["value"] = target_value
    target_entry["produced_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if notes:
        target_entry["notes"] = notes
    if target_gpu:
        current_env["gpu"] = target_gpu
        target_entry["environment"] = current_env

    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    print(f"SUCCESS: Promoted [{eid}] to MEASURED.")
    print(f"  source_file: {src_str}")
    print(f"  sha256:      {computed_hash}")
    print(f"  value:       {target_value}")
    if target_gpu:
        print(f"  gpu:         {target_gpu}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Claims Ledger Tool.")
    subparsers = parser.add_subparsers(dest="command", help="Ledger action")

    # verify
    subparsers.add_parser("verify", help="Recompute hashes, fail on any violation")

    # summary
    subparsers.add_parser("summary", help="Print counts of MEASURED / SIMULATED / PENDING")

    # list
    list_p = subparsers.add_parser("list", help="List entries, optionally filtered by status")
    list_p.add_argument("status", nargs="?", default=None, help="Filter by status (MEASURED/SIMULATED/PENDING)")

    # promote
    promote_p = subparsers.add_parser("promote", help="Promote a ledger claim from PENDING to MEASURED")
    promote_p.add_argument("id", help="Ledger claim ID to promote")
    promote_p.add_argument("--source", "-s", default=None, help="Path to evidence source file")
    promote_p.add_argument("--gpu", default=None, help="Real hardware GPU name (mandatory for hardware claims)")
    promote_p.add_argument("--value", "-v", default=None, help="Measured value")
    promote_p.add_argument("--notes", default=None, help="Provenance or audit notes")
    promote_p.add_argument("--dry-run", action="store_true", help="Preview promotion without writing changes")

    args = parser.parse_args()

    if not args.command or args.command == "verify":
        cmd_verify()
    elif args.command == "summary":
        cmd_summary()
    elif args.command == "list":
        cmd_list(args.status)
    elif args.command == "promote":
        cmd_promote(
            entry_id=args.id,
            source_file=args.source,
            gpu=args.gpu,
            value=args.value,
            notes=args.notes,
            dry_run=args.dry_run,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
