"""Performance and latency benchmarks (TC-25, TC-26, TC-28)."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import numpy as np
import psutil
import pytest

from sentinel.config import FrameDimensions, RulesConfig, ZoneDefinition, ZonesConfig
from sentinel.domain.models import Box, Detection, FrameMeta
from sentinel.domain.rules import RuleEngine
from sentinel.domain.zones import ZoneManager
from sentinel.ports.clock import InjectedClock


@pytest.mark.tc("TC-26")
def test_tc26_rule_engine_high_throughput_cpu():
    """TC-26: Rule engine processes 25 FPS with 20 persons under 15% single CPU core (p99 < 5ms)."""
    zones_cfg = ZonesConfig(
        frame=FrameDimensions(width=1920, height=1080),
        zones=[
            ZoneDefinition(
                id="restricted-zone",
                type="restricted",
                required_ppe=["helmet", "vest"],
                polygon=[[200, 200], [1600, 200], [1600, 900], [200, 900]],
            ),
            ZoneDefinition(
                id="danger-zone",
                type="danger",
                required_ppe=["helmet", "vest"],
                polygon=[[500, 300], [1000, 300], [1000, 700], [500, 700]],
            ),
        ],
    )
    rules_cfg = RulesConfig()
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=ZoneManager(zones_cfg))

    num_frames = 500
    num_persons = 20
    step_times_ms: List[float] = []

    # Pre-generate 500 frames of 20 people with helmets and vests
    frames: List[FrameMeta] = []
    for f_idx in range(num_frames):
        ts = f_idx * 0.04
        dets: List[Detection] = []
        for p in range(num_persons):
            bx = 250.0 + (p * 60.0) % 1200.0
            by = 250.0 + (p * 25.0) % 600.0
            dets.append(
                Detection(
                    class_name="person",
                    conf=0.92,
                    box=Box(bx, by, bx + 60, by + 180),
                    track_id=p + 1,
                )
            )
            dets.append(
                Detection(class_name="helmet", conf=0.95, box=Box(bx + 5, by + 5, bx + 55, by + 45))
            )
            dets.append(
                Detection(class_name="vest", conf=0.90, box=Box(bx + 5, by + 50, bx + 55, by + 120))
            )
        frames.append(FrameMeta(ts=ts, frame_id=f_idx, camera_id="cam-01", detections=dets))

    # Benchmark loop
    for frame in frames:
        t0 = time.perf_counter()
        engine.process_frame(frame)
        t1 = time.perf_counter()
        step_times_ms.append((t1 - t0) * 1000.0)

    avg_step_ms = float(np.mean(step_times_ms))
    p99_step_ms = float(np.percentile(step_times_ms, 99))
    max_step_ms = float(np.max(step_times_ms))

    # Assert budget:
    # 25 FPS = 40 ms per frame. 15% of 1 CPU core = 6.0 ms.
    # Requirement: p99 under 5.0 ms, average under 6.0 ms
    assert p99_step_ms < 5.0, f"p99 step time {p99_step_ms:.2f} ms exceeds 5.0 ms threshold"
    assert avg_step_ms < 6.0, f"Average step time {avg_step_ms:.2f} ms exceeds 6.0 ms budget"

    # Record perf report
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_file = Path(f"reports/perf_{today_str}.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_content = f"""# SiteSentinel Performance Benchmark Report ({today_str})

## Test Environment
- Host: {os.uname().sysname} {os.uname().machine}
- Python: {sys.version.split()[0]}
- Profiling mode: REAL CPU Profiling

## TC-26 Rule Engine Throughput (20 Persons, 25 FPS)
- **Frames Evaluated**: {num_frames}
- **Simultaneous Persons**: {num_persons}
- **Detections per Frame**: {num_persons * 3}
- **Average Step Time**: {avg_step_ms:.3f} ms (Target < 6.0 ms)
- **p99 Step Time**: {p99_step_ms:.3f} ms (Target < 5.0 ms)
- **Max Step Time**: {max_step_ms:.3f} ms
- **Equivalent FPS**: {1000.0 / avg_step_ms:.1f} FPS
- **Core Utilization at 25 FPS**: {(avg_step_ms / 40.0) * 100.0:.2f}% (Target < 15%)
- **Result**: PASS
"""
    report_file.write_text(report_content, encoding="utf-8")


@pytest.mark.tc("TC-25")
def test_tc25_violation_start_to_publish_latency():
    """TC-25: Violation start to MQTT publish under 3.0s including debounce on injected clock."""
    zones_cfg = ZonesConfig(
        frame=FrameDimensions(width=1920, height=1080),
        zones=[
            ZoneDefinition(
                id="helmet-zone",
                type="safe",
                required_ppe=["helmet"],
                polygon=[[100, 100], [1000, 100], [1000, 1000], [100, 1000]],
            )
        ],
    )
    rules_cfg = RulesConfig()
    rules_cfg.no_helmet.min_duration_s = 2.0  # 2.0s debounce

    clock = InjectedClock(initial_ts=100.0)
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=ZoneManager(zones_cfg))

    violation_start_ts = clock.now()
    published_ts = None
    incidents = []

    # Feed frames at 25 FPS (0.04s per frame)
    for step in range(65):
        frame = FrameMeta(
            ts=clock.now(),
            frame_id=step,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.9, box=Box(200, 200, 280, 500), track_id=42)
            ],
        )
        res = engine.process_frame(frame)
        if res:
            published_ts = clock.now()
            incidents.extend(res)
            break
        clock.advance(0.04)

    assert len(incidents) == 1, "Incident must trigger once debounce period elapses"
    assert published_ts is not None
    latency_s = published_ts - violation_start_ts

    # Latency threshold: under 3.0s including 2.0s debounce
    assert latency_s <= 3.0, f"Latency {latency_s:.2f}s exceeded 3.0s target"
    assert latency_s >= 2.0, "Latency must account for debounce"


@pytest.mark.tc("TC-28")
def test_tc28_memory_bounded_soak():
    """TC-28: Memory bounded under sustained frame processing and track purging."""
    process = psutil.Process(os.getpid())
    rss_start = process.memory_info().rss / (1024 * 1024)

    zones_cfg = ZonesConfig(
        frame=FrameDimensions(width=1920, height=1080),
        zones=[
            ZoneDefinition(
                id="safe",
                type="safe",
                required_ppe=["helmet"],
                polygon=[[0, 0], [1920, 0], [1920, 1080], [0, 1080]],
            )
        ],
    )
    rules_cfg = RulesConfig()
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=ZoneManager(zones_cfg))

    # Process 2,000 frames with rotating tracks (churn tracks to test purging)
    for f in range(2000):
        ts = f * 0.04
        t_id = f // 25  # New track ID every second (25 frames)
        frame = FrameMeta(
            ts=ts,
            frame_id=f,
            camera_id="cam-01",
            detections=[
                Detection(
                    class_name="person", conf=0.9, box=Box(100, 100, 200, 400), track_id=t_id
                ),
                Detection(class_name="helmet", conf=0.9, box=Box(110, 105, 190, 180)),
            ],
        )
        engine.process_frame(frame)

    rss_end = process.memory_info().rss / (1024 * 1024)
    delta_mb = rss_end - rss_start

    # Verify inactive tracks purged and memory increase is bounded (< 15 MB)
    assert delta_mb < 15.0, f"Memory leak detected: RSS increased by {delta_mb:.2f} MB"
