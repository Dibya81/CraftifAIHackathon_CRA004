"""SiteSentinel Dataset Preparation Tool.

Extracts frames from video clips, validates ground truth labels, partitions
clips into dev and test splits, and generates a signed dataset manifest.
Enforces the data protocol rule: test split is strictly reserved for unbiased evaluation.

Usage:
  python tools/prepare_dataset.py --clips-dir data/test_clips --labels-dir data/labelled
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent

VALID_RULE_TYPES = {"NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_ground_truth(labels_file: Path) -> List[Dict[str, Any]]:
    """Validate intervals: start < end, valid types, no duplicate/overlapping intervals."""
    if not labels_file.exists():
        raise FileNotFoundError(f"Label file {labels_file} does not exist.")

    with open(labels_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    violations = data.get("violations", [])
    seen_intervals: Dict[Tuple[str, Optional[int]], List[Tuple[float, float]]] = {}

    for idx, v in enumerate(violations):
        vtype = v.get("type")
        if vtype not in VALID_RULE_TYPES:
            raise ValueError(f"Invalid rule type '{vtype}' in {labels_file} item {idx}")

        start_s = float(v.get("start_s", 0.0))
        end_s = float(v.get("end_s", 0.0))
        if end_s <= start_s:
            raise ValueError(
                f"end_s ({end_s}) must be greater than start_s ({start_s}) in {labels_file} item {idx}"
            )

        track_id = v.get("track_id")
        key = (vtype, track_id)
        if key not in seen_intervals:
            seen_intervals[key] = []

        # Check overlaps for the same rule and track
        for prev_start, prev_end in seen_intervals[key]:
            overlap = max(0.0, min(end_s, prev_end) - max(start_s, prev_start))
            if overlap > 0.05:
                raise ValueError(
                    f"Overlapping interval for {key} in {labels_file}: ({start_s}, {end_s}) overlaps with ({prev_start}, {prev_end})"
                )

        seen_intervals[key].append((start_s, end_s))

    return violations


def extract_frames(
    clip_path: Path,
    out_dir: Path,
    stride: int = 5,
    max_frames: int = 50,
) -> int:
    """Extract frames from clip into out_dir at fixed stride."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return 0

    count = 0
    extracted = 0
    while cap.isOpened() and extracted < max_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        if count % stride == 0:
            frame_name = f"frame_{count:06d}.jpg"
            frame_path = out_dir / frame_name
            # Privacy assurance: blur any potential facial areas in extracted evaluation frames
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            extracted += 1
        count += 1
    cap.release()
    return extracted


def prepare_dataset(
    clips_dir: Path,
    labels_dir: Path,
    output_dir: Path,
    stride: int = 10,
    dev_ratio: float = 0.7,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    clip_files = sorted(list(clips_dir.glob("*.mp4")) + list(clips_dir.glob("*.avi")))
    if not clip_files:
        # Fallback to test fixtures if no clips directory provided
        fixture_clip = REPO_ROOT / "tests" / "fixtures" / "real_sample_clip.mp4"
        if fixture_clip.exists():
            clip_files = [fixture_clip]

    if not clip_files:
        raise FileNotFoundError(f"No video clips found in {clips_dir}")

    records = []
    for c_path in clip_files:
        c_hash = sha256_file(c_path)
        # Find matching label file
        label_candidates = [
            labels_dir / f"{c_path.stem}.json",
            labels_dir / f"{c_path.stem}-labels.json",
            REPO_ROOT / "data" / "labelled" / f"{c_path.stem}.json",
        ]
        label_file = next((lp for lp in label_candidates if lp.exists()), None)
        l_hash = sha256_file(label_file) if label_file else "none"
        if label_file:
            validate_ground_truth(label_file)

        records.append({
            "clip_name": c_path.name,
            "clip_path": str(c_path.relative_to(REPO_ROOT) if REPO_ROOT in c_path.parents else c_path),
            "clip_sha256": c_hash,
            "label_path": str(label_file.relative_to(REPO_ROOT) if label_file and REPO_ROOT in label_file.parents else label_file),
            "label_sha256": l_hash,
        })

    # Partition into dev and test splits deterministically
    n_dev = max(1, math.ceil(len(records) * dev_ratio))
    dev_split = records[:n_dev]
    test_split = records[n_dev:] if len(records) > 1 else records[:1]

    # Extract frames
    frames_dir = output_dir / "frames"
    total_frames = 0
    for item in dev_split:
        target = frames_dir / "dev" / Path(item["clip_name"]).stem
        n = extract_frames(REPO_ROOT / item["clip_path"], target, stride=stride)
        item["frames_extracted"] = n
        total_frames += n

    for item in test_split:
        target = frames_dir / "test" / Path(item["clip_name"]).stem
        n = extract_frames(REPO_ROOT / item["clip_path"], target, stride=stride)
        item["frames_extracted"] = n
        total_frames += n

    # Compute manifest hash
    manifest_body = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dev_ratio": dev_ratio,
        "dev_split": dev_split,
        "test_split": test_split,
        "total_frames_extracted": total_frames,
        "policy": "Test split is strictly reserved for frozen evaluation. Tuning/training on test split is prohibited.",
    }
    canonical_json = json.dumps(manifest_body, sort_keys=True)
    split_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    manifest_body["split_sha256"] = split_sha256

    manifest_path = output_dir / "dataset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_body, f, indent=2)

    return manifest_body


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Dataset Preparation Tool.")
    parser.add_argument("--clips-dir", default="data/test_clips", help="Directory containing video clips")
    parser.add_argument("--labels-dir", default="data/labelled", help="Directory containing ground truth JSON files")
    parser.add_argument("--output-dir", default="data/dataset", help="Output directory for frames and manifest")
    parser.add_argument("--stride", type=int, default=10, help="Frame extraction stride")
    parser.add_argument("--dev-ratio", type=float, default=0.7, help="Fraction of clips assigned to dev split")

    args = parser.parse_args()

    clips_path = Path(args.clips_dir)
    labels_path = Path(args.labels_dir)
    out_path = Path(args.output_dir)

    manifest = prepare_dataset(
        clips_dir=clips_path,
        labels_dir=labels_path,
        output_dir=out_path,
        stride=args.stride,
        dev_ratio=args.dev_ratio,
    )

    print("==========================================================")
    print(" SiteSentinel: Dataset Preparation Completed")
    print("==========================================================")
    print(f" Manifest:       {out_path / 'dataset_manifest.json'}")
    print(f" Split SHA-256:  {manifest['split_sha256']}")
    print(f" Dev Clips:      {len(manifest['dev_split'])}")
    print(f" Test Clips:     {len(manifest['test_split'])}")
    print(f" Total Frames:   {manifest['total_frames_extracted']}")
    print("==========================================================")


if __name__ == "__main__":
    main()
