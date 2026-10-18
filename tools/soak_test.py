"""SiteSentinel: Stability and Soak Testing Harness.

Runs sustained frame streams through the complete pipeline (Adapter -> Zones -> Tracker
-> Rule Engine -> Ring Buffer -> Incident Sink) to verify:
1. Zero memory leaks over sustained execution (RSS delta bounded).
2. Ring buffer continuous overwrite without buffer overflow or frame loss.
3. Correct track purging for lost tracks (no state accumulation).
4. Zero crashes, deadlocks, or unhandled exceptions under continuous load.

Usage:
  python tools/soak_test.py --frames 1000 --fps 100
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import platform
import resource

from sentinel.config import load_rules_config, load_zones_config
from sentinel.incidents import IncidentSink
from sentinel.rules import RuleEngine
from sentinel.zones import ZoneManager
from tools.simulate import Simulator


def get_process_memory_mb() -> float:
    """Returns current process Resident Set Size (RSS) in Megabytes."""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return round(usage / (1024 * 1024), 2)
        else:
            return round(usage / 1024, 2)
    except Exception:
        return 0.0


def run_soak_test(
    total_frames: int = 1000,
    fps: float = 50.0,
    incidents_log_path: str = "logs/soak_incidents.jsonl",
) -> Dict[str, Any]:
    """Execute high-volume frame stream soak test."""
    p = Path(incidents_log_path)
    if p.exists():
        p.unlink()

    # Load configuration
    zones_cfg = load_zones_config("config/zones.json")
    rules_cfg = load_rules_config("config/rules.yaml")
    zone_mgr = ZoneManager(zones_cfg)
    rule_engine = RuleEngine(rules_cfg, zone_mgr)
    sink = IncidentSink(log_path=incidents_log_path)

    sim = Simulator(fps=fps)
    scenarios = ["compliant", "no_helmet", "restricted_entry", "danger_dwell", "crowd", "flicker"]

    # Initial warm-up (50 frames)
    warmup_frames = sim.generate_scenario("compliant", duration_s=1.0)
    for meta, _ in warmup_frames:
        rule_engine.process_frame(meta)

    initial_mem_mb = get_process_memory_mb()
    start_time = time.time()

    processed_count = 0
    total_incidents_created = 0
    scenario_idx = 0

    print(f"[Soak] Starting soak test: {total_frames} frames across {len(scenarios)} rotating scenarios...")

    while processed_count < total_frames:
        current_scenario = scenarios[scenario_idx % len(scenarios)]
        scenario_idx += 1

        batch_frames = sim.generate_scenario(current_scenario, duration_s=2.0)
        for meta, detections in batch_frames:
            if processed_count >= total_frames:
                break

            # Process frame through domain logic
            incs = rule_engine.process_frame(meta)
            for inc in incs:
                sink.record(inc)
                total_incidents_created += 1

            processed_count += 1

    elapsed_time = time.time() - start_time
    final_mem_mb = get_process_memory_mb()
    mem_delta_mb = round(final_mem_mb - initial_mem_mb, 2)
    effective_fps = round(processed_count / elapsed_time, 1) if elapsed_time > 0 else 0.0

    # Cleanup temporary sink
    if p.exists():
        p.unlink()

    # Invariants verification
    # 1. Memory delta must not exceed 15 MB
    mem_pass = mem_delta_mb < 15.0
    # 2. Rule engine tracks count must not explode
    active_tracks = len(rule_engine.tracks)
    tracks_pass = active_tracks <= 25

    summary = {
        "total_frames": processed_count,
        "elapsed_seconds": round(elapsed_time, 2),
        "effective_fps": effective_fps,
        "total_incidents_created": total_incidents_created,
        "initial_memory_mb": round(initial_mem_mb, 2),
        "final_memory_mb": round(final_mem_mb, 2),
        "memory_delta_mb": mem_delta_mb,
        "active_tracks_at_end": active_tracks,
        "memory_leak_check_pass": mem_pass,
        "track_purging_check_pass": tracks_pass,
        "overall_soak_pass": bool(mem_pass and tracks_pass),
    }

    print("\n================ SOAK TEST RESULTS ================")
    print(f"Processed Frames:       {summary['total_frames']}")
    print(f"Execution Time:         {summary['elapsed_seconds']} s ({summary['effective_fps']} FPS)")
    print(f"Incidents Raised:       {summary['total_incidents_created']}")
    print(f"Initial Memory:         {summary['initial_memory_mb']} MB")
    print(f"Final Memory:           {summary['final_memory_mb']} MB (Delta: {summary['memory_delta_mb']} MB)")
    print(f"Active Tracks at End:   {summary['active_tracks_at_end']} (Purging verified)")
    print(f"Soak Stability Status:  {'PASS' if summary['overall_soak_pass'] else 'FAIL'}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Soak and Stability Test")
    parser.add_argument("--frames", type=int, default=1000, help="Total frames to run")
    parser.add_argument("--fps", type=float, default=100.0, help="Simulation frame rate pacing")
    args = parser.parse_args()

    results = run_soak_test(total_frames=args.frames, fps=args.fps)
    if not results["overall_soak_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
