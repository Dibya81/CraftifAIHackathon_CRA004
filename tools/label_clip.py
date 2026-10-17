"""SiteSentinel: Ground truth clip labelling tool.

Allows defining and validating ground-truth violation intervals for offline evaluation.
Usage:
  python tools/label_clip.py --clip data/test_clips/site01.mp4 --out data/labelled/site01.json \
    --add "NO_HELMET:2.0:6.0:1:press-area" \
    --add "ZONE_INTRUSION:8.0:12.0:2:crane-drop"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2

VALID_VIOLATION_TYPES = {"NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"}


def parse_interval_spec(spec: str) -> Dict[str, Any]:
    """Parse interval string formatted as 'TYPE:START_S:END_S[:TRACK_ID][:ZONE]'."""
    parts = spec.strip().split(":")
    if len(parts) < 3:
        raise ValueError(
            f"Invalid interval spec '{spec}'. Must be TYPE:START_S:END_S[:TRACK_ID][:ZONE]"
        )

    v_type = parts[0].upper()
    if v_type not in VALID_VIOLATION_TYPES:
        raise ValueError(
            f"Invalid violation type '{v_type}'. Allowed: {sorted(VALID_VIOLATION_TYPES)}"
        )

    try:
        start_s = float(parts[1])
        end_s = float(parts[2])
    except ValueError as e:
        raise ValueError(f"Start and end timestamps must be floats in '{spec}'") from e

    if end_s <= start_s:
        raise ValueError(f"end_s ({end_s}) must be greater than start_s ({start_s})")

    track_id: Optional[int] = None
    if len(parts) >= 4 and parts[3].strip():
        try:
            track_id = int(parts[3])
        except ValueError:
            pass

    zone: Optional[str] = None
    if len(parts) >= 5 and parts[4].strip():
        zone = parts[4].strip()

    res: Dict[str, Any] = {
        "type": v_type,
        "start_s": round(start_s, 2),
        "end_s": round(end_s, 2),
    }
    if track_id is not None:
        res["track_id"] = track_id
    if zone is not None:
        res["zone"] = zone

    return res


def inspect_clip(clip_path: str | Path) -> Dict[str, Any]:
    """Extract metadata from video clip (duration, fps, frame count, dimensions)."""
    p = Path(clip_path)
    if not p.exists():
        return {
            "clip": str(p),
            "fps": 25.0,
            "frame_count": 500,
            "duration_s": 20.0,
            "width": 1920,
            "height": 1080,
        }

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        return {
            "clip": str(p),
            "fps": 25.0,
            "frame_count": 0,
            "duration_s": 0.0,
            "width": 1920,
            "height": 1080,
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
    duration_s = round(frame_count / fps, 2) if fps > 0 else 0.0
    cap.release()

    return {
        "clip": str(p),
        "fps": round(fps, 2),
        "frame_count": frame_count,
        "duration_s": duration_s,
        "width": w,
        "height": h,
    }


def save_labels(
    output_path: str | Path,
    clip_info: Dict[str, Any],
    violations: List[Dict[str, Any]],
) -> Path:
    """Save ground truth JSON structure."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "clip": clip_info.get("clip", ""),
        "fps": clip_info.get("fps", 25.0),
        "frame_count": clip_info.get("frame_count", 0),
        "duration_s": clip_info.get("duration_s", 0.0),
        "violations": sorted(violations, key=lambda v: v["start_s"]),
    }

    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return out_p


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Ground Truth Clip Labeller")
    parser.add_argument("--clip", type=str, required=True, help="Path to video clip")
    parser.add_argument("--out", type=str, required=True, help="Path to output ground-truth JSON")
    parser.add_argument(
        "--add",
        action="append",
        type=str,
        default=[],
        help="Add violation interval 'TYPE:START_S:END_S[:TRACK_ID][:ZONE]'",
    )
    args = parser.parse_args()

    clip_info = inspect_clip(args.clip)
    violations: List[Dict[str, Any]] = []

    # If output file already exists, load existing violations
    out_path = Path(args.out)
    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                violations = existing.get("violations", [])
        except Exception:
            violations = []

    for spec in args.add:
        parsed = parse_interval_spec(spec)
        violations.append(parsed)

    saved = save_labels(out_path, clip_info, violations)
    print(f"Saved {len(violations)} ground-truth intervals to {saved}")


if __name__ == "__main__":
    main()
