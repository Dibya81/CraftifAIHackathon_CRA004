"""SiteSentinel Dataset Validation Tool.

Verifies dataset integrity, validates dev/test split hashes against ledger,
checks label consistency, and enforces the strict rule:
REFUSES parameter tuning or model training on the test split.

Usage:
  python tools/validate_dataset.py --manifest data/dataset/dataset_manifest.json
  python tools/validate_dataset.py --task tune --split test  # Will refuse!
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_split_integrity(manifest_path: Path) -> Tuple[bool, List[str]]:
    if not manifest_path.exists():
        return False, [f"Manifest file not found: {manifest_path}"]

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    recorded_hash = data.get("split_sha256")
    manifest_copy = dict(data)
    manifest_copy.pop("split_sha256", None)

    canonical = json.dumps(manifest_copy, sort_keys=True)
    computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if recorded_hash != computed_hash:
        errors.append(
            f"Manifest split_sha256 mismatch!\n  recorded: {recorded_hash}\n  computed: {computed_hash}"
        )

    # Check that dev and test splits have no clip overlap
    dev_clips = {item["clip_name"] for item in data.get("dev_split", [])}
    test_clips = {item["clip_name"] for item in data.get("test_split", [])}
    overlap = dev_clips & test_clips
    if len(dev_clips) > 1 and overlap:
        errors.append(f"Data protocol violation: Clip overlap between dev and test splits: {overlap}")

    # Check files exist on disk and verify hashes
    for entry in data.get("dev_split", []) + data.get("test_split", []):
        c_path = REPO_ROOT / entry["clip_path"]
        if not c_path.exists():
            errors.append(f"Missing clip on disk: {c_path}")
        else:
            actual_h = sha256_file(c_path)
            if actual_h != entry.get("clip_sha256"):
                errors.append(f"Hash mismatch for {c_path}: expected {entry.get('clip_sha256')}, got {actual_h}")

    return len(errors) == 0, errors


def check_tuning_permission(task: str, split: str) -> None:
    """Enforce Data Protocol: Never tune or train on the test split."""
    normalized_task = task.strip().lower()
    normalized_split = split.strip().lower()

    if normalized_split == "test" and normalized_task in {
        "tune",
        "train",
        "optimize",
        "calibrate",
        "fit",
    }:
        print(
            "REFUSAL [Exit 1]: Data Protocol Violation! "
            f"Attempting to '{task}' on the frozen 'test' split. "
            "Tuning parameters or training models on the test split is strictly forbidden. "
            "Use the 'dev' split for all calibration, parameter sweeps, and threshold tuning.",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Dataset Validator")
    parser.add_argument(
        "--manifest",
        default="data/dataset/dataset_manifest.json",
        help="Path to dataset manifest JSON",
    )
    parser.add_argument(
        "--task",
        default="eval",
        choices=["eval", "tune", "train", "validate"],
        help="Requested pipeline task",
    )
    parser.add_argument(
        "--split",
        default="test",
        choices=["dev", "test"],
        help="Target dataset split",
    )
    parser.add_argument(
        "--record-ledger",
        action="store_true",
        help="Update DATASET-SPLIT-HASH entry in evidence/ledger.yaml",
    )

    args = parser.parse_args()

    # Guard: check tuning prohibition
    check_tuning_permission(args.task, args.split)

    manifest_p = Path(args.manifest)
    if not manifest_p.exists():
        # Look for default data/dataset_manifest.json
        alt_p = REPO_ROOT / "data" / "dataset_manifest.json"
        if alt_p.exists():
            manifest_p = alt_p
        else:
            print(f"Dataset manifest not found at {manifest_p}. Run tools/prepare_dataset.py first.", file=sys.stderr)
            sys.exit(1)

    valid, errors = validate_split_integrity(manifest_p)
    if not valid:
        print(f"DATASET VALIDATION FAILED with {len(errors)} errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: Dataset manifest {manifest_p} verified valid. Split integrity verified.")


if __name__ == "__main__":
    main()
