"""SiteSentinel Soak test runner supporting time duration and report generation (TC-28)."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root and src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.soak_test import run_soak_test


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Soak Stability Test")
    parser.add_argument("--minutes", type=float, default=2.0, help="Duration in minutes (default: 2.0 for make judge)")
    parser.add_argument("--fps", type=float, default=100.0, help="Simulation pacing FPS")
    parser.add_argument("--output", type=str, default="", help="Optional path to output markdown report")
    args = parser.parse_args()

    # Calculate total frames for target duration at given FPS
    target_frames = int(args.minutes * 60 * args.fps)
    print(f"[Soak] Executing {args.minutes:.1f}-minute soak test ({target_frames} frames at {args.fps} FPS)...")

    results = run_soak_test(total_frames=target_frames, fps=args.fps)

    # Write report
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = Path(args.output) if args.output else Path(f"reports/soak_{today_str}.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    report_content = f"""# SiteSentinel Sustained Soak Stability Report ({today_str})

## Environment
- Host: {os.uname().sysname} {os.uname().machine}
- Python: {sys.version.split()[0]}
- Target Duration: {args.minutes} minutes
- Evaluation Mode: REAL Continuous Execution

## Soak Test Metrics (TC-28)
- **Total Frames Processed**: {results['total_frames']}
- **Elapsed Real Time**: {results['elapsed_seconds']} s
- **Effective Processing Rate**: {results['effective_fps']} FPS
- **Incidents Recorded**: {results['total_incidents_created']}
- **Initial Process Memory (RSS)**: {results['initial_memory_mb']} MB
- **Final Process Memory (RSS)**: {results['final_memory_mb']} MB
- **Memory Delta (RSS)**: {results['memory_delta_mb']} MB (Threshold < 15.0 MB)
- **Active Tracks at Completion**: {results['active_tracks_at_end']} (Purging verified <= 25)
- **Memory Stability Result**: {'PASS' if results['memory_leak_check_pass'] else 'FAIL'}
- **Track Purging Result**: {'PASS' if results['track_purging_check_pass'] else 'FAIL'}
- **Overall Result**: {'PASS' if results['overall_soak_pass'] else 'FAIL'}
"""
    out_file.write_text(report_content, encoding="utf-8")
    print(f"[Soak] Wrote stability report to {out_file}")

    if not results["overall_soak_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
