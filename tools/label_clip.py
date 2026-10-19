"""SiteSentinel: Ground Truth Clip Labelling Tool.

Allows defining, validating, and interactively labelling ground-truth violation intervals
for offline evaluation on real or simulated video clips.

Features:
- Keyboard-driven interactive labelling and terminal workflow.
- Undo capability (undo last interval or session history).
- Interval validation: start < end, inside clip duration, no overlapping intervals for same person/rule.
- Tracker-independent ground truth export format:
  {
    "person": "worker-1",
    "rule_type": "NO_HELMET",
    "zone": "walkway",
    "start_s": 2.5,
    "end_s": 7.0
  }

Usage:
  python tools/label_clip.py --clip data/test_clips/site01.mp4 --out data/labelled/site01.json \
    --add "NO_HELMET:2.0:6.0:worker-1:press-area"
  python tools/label_clip.py --clip data/test_clips/site01.mp4 --out data/labelled/site01.json --interactive
  python tools/label_clip.py --out data/labelled/site01.json --undo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

VALID_VIOLATION_TYPES = {"NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"}


def parse_interval_spec(spec: str, max_duration: Optional[float] = None) -> Dict[str, Any]:
    """Parse interval string formatted as 'TYPE:START_S:END_S[:PERSON_OR_TRACK][:ZONE]'."""
    parts = spec.strip().split(":")
    if len(parts) < 3:
        raise ValueError(
            f"Invalid interval spec '{spec}'. Must be TYPE:START_S:END_S[:PERSON][:ZONE]"
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
        raise ValueError(f"end_s ({end_s}) must be strictly greater than start_s ({start_s})")

    if max_duration is not None and (start_s > max_duration or end_s > max_duration + 0.5):
        raise ValueError(
            f"Interval ({start_s}, {end_s}) exceeds clip duration ({max_duration}s)"
        )

    person = "worker-1"
    track_id: Optional[int] = None
    if len(parts) >= 4 and parts[3].strip():
        raw_p = parts[3].strip()
        person = raw_p
        try:
            track_id = int(raw_p)
        except ValueError:
            pass

    zone = "default"
    if len(parts) >= 5 and parts[4].strip():
        zone = parts[4].strip()

    res: Dict[str, Any] = {
        "person": person,
        "rule_type": v_type,
        "type": v_type,
        "start_s": round(start_s, 2),
        "end_s": round(end_s, 2),
        "zone": zone,
    }
    if track_id is not None:
        res["track_id"] = track_id

    return res


def validate_intervals(violations: List[Dict[str, Any]], max_duration: Optional[float] = None) -> None:
    """Validate list of intervals for ordering, bounds, and overlaps per person/rule."""
    seen: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}

    for idx, v in enumerate(violations):
        rule = v.get("rule_type") or v.get("type", "UNKNOWN")
        person = str(v.get("person") or v.get("track_id") or "worker-1")
        start = float(v.get("start_s", 0.0))
        end = float(v.get("end_s", 0.0))

        if end <= start:
            raise ValueError(f"Item {idx}: end_s ({end}) must be greater than start_s ({start})")

        if max_duration is not None and (start > max_duration or end > max_duration + 0.5):
            raise ValueError(f"Item {idx}: interval ({start}, {end}) exceeds duration {max_duration}s")

        key = (rule, person)
        if key not in seen:
            seen[key] = []

        for p_start, p_end in seen[key]:
            overlap = max(0.0, min(end, p_end) - max(start, p_start))
            if overlap > 0.05:
                raise ValueError(
                    f"Overlapping interval for {person} / {rule}: ({start}, {end}) overlaps with ({p_start}, {p_end})"
                )

        seen[key].append((start, end))


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
    """Save validated ground truth JSON structure."""
    validate_intervals(violations, clip_info.get("duration_s"))
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


def run_interactive_session(
    clip_info: Dict[str, Any],
    existing_violations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Runs a keyboard-driven interactive CLI session for labeling without requiring GUI."""
    violations = list(existing_violations)
    history: List[List[Dict[str, Any]]] = [list(violations)]

    print("\n==========================================================")
    print(" SiteSentinel: Interactive Ground-Truth Labelling")
    print(f" Clip: {clip_info['clip']} ({clip_info['duration_s']}s, {clip_info['fps']} FPS)")
    print(" Commands: [a]dd, [u]ndo, [l]ist, [q]uit and save")
    print("==========================================================")

    while True:
        try:
            cmd = input("\nAction [a/u/l/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == "q":
            break
        elif cmd == "l":
            print(f"Current intervals ({len(violations)}):")
            for i, v in enumerate(violations):
                print(f"  {i + 1}. [{v['rule_type']}] {v['person']} in '{v['zone']}': {v['start_s']}s - {v['end_s']}s")
        elif cmd == "u":
            if len(history) > 1:
                history.pop()
                violations = list(history[-1])
                print(f"Undone. Remaining intervals: {len(violations)}")
            elif violations:
                violations.pop()
                print(f"Popped last item. Remaining: {len(violations)}")
            else:
                print("Nothing to undo.")
        elif cmd == "a":
            print("Select Rule Type:")
            rule_list = sorted(VALID_VIOLATION_TYPES)
            for idx, r in enumerate(rule_list, 1):
                print(f"  [{idx}] {r}")
            r_choice = input("Rule [1-4]: ").strip()
            try:
                rule_type = rule_list[int(r_choice) - 1]
            except Exception:
                print("Invalid rule selection.")
                continue

            person = input("Person identifier [worker-1]: ").strip() or "worker-1"
            zone = input("Zone name [walkway]: ").strip() or "walkway"
            start_str = input("Start timestamp in seconds: ").strip()
            end_str = input("End timestamp in seconds: ").strip()

            spec = f"{rule_type}:{start_str}:{end_str}:{person}:{zone}"
            try:
                parsed = parse_interval_spec(spec, clip_info.get("duration_s"))
                test_list = list(violations) + [parsed]
                validate_intervals(test_list, clip_info.get("duration_s"))
                violations.append(parsed)
                history.append(list(violations))
                print(f"Added interval: {parsed['rule_type']} {start_str}s -> {end_str}s")
            except Exception as e:
                print(f"Error adding interval: {e}")

    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Ground Truth Clip Labeller")
    parser.add_argument("--clip", type=str, default="", help="Path to video clip")
    parser.add_argument("--out", type=str, required=True, help="Path to output ground-truth JSON")
    parser.add_argument(
        "--add",
        action="append",
        type=str,
        default=[],
        help="Add violation interval 'TYPE:START_S:END_S[:PERSON][:ZONE]'",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Remove the last recorded interval from the output JSON",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run keyboard-driven interactive labelling session",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    clip_info = inspect_clip(args.clip) if args.clip else {}
    violations: List[Dict[str, Any]] = []

    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                violations = existing.get("violations", [])
                if not clip_info:
                    clip_info = {
                        "clip": existing.get("clip", ""),
                        "fps": existing.get("fps", 25.0),
                        "frame_count": existing.get("frame_count", 0),
                        "duration_s": existing.get("duration_s", 0.0),
                    }
        except Exception:
            violations = []

    if args.undo:
        if violations:
            popped = violations.pop()
            save_labels(out_path, clip_info, violations)
            print(f"Undid interval: {popped}")
        else:
            print("No intervals to undo in file.")
        return

    for spec in args.add:
        parsed = parse_interval_spec(spec, clip_info.get("duration_s"))
        violations.append(parsed)

    if args.interactive:
        violations = run_interactive_session(clip_info, violations)

    saved = save_labels(out_path, clip_info, violations)
    print(f"Saved {len(violations)} ground-truth intervals to {saved}")


if __name__ == "__main__":
    main()
