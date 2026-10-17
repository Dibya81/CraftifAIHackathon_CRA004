"""Benchmark test: verifies rule engine processes 25 FPS with 20 simultaneous persons

using under 15% of one CPU core (< 6 ms per frame budget).
"""

import time

from sentinel.config import FrameDimensions, RulesConfig, ZoneDefinition, ZonesConfig
from sentinel.models import Box, Detection, FrameMeta
from sentinel.rules import RuleEngine
from sentinel.zones import ZoneManager


def test_rule_engine_throughput_benchmark():
    zones_cfg = ZonesConfig(
        frame=FrameDimensions(width=1920, height=1080),
        zones=[
            ZoneDefinition(
                id="walkway",
                type="safe",
                required_ppe=["helmet"],
                polygon=[[100, 600], [900, 600], [900, 1000], [100, 1000]],
            ),
            ZoneDefinition(
                id="press-area",
                type="restricted",
                required_ppe=["helmet", "vest"],
                polygon=[[1000, 300], [1700, 300], [1700, 900], [1000, 900]],
            ),
            ZoneDefinition(
                id="crane-drop",
                type="danger",
                required_ppe=["helmet", "vest"],
                polygon=[[1200, 100], [1500, 100], [1500, 300], [1200, 300]],
            ),
        ],
    )
    rules_cfg = RulesConfig()
    engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=ZoneManager(zones_cfg))

    # Generate 500 frames (~20 seconds of 25 FPS video) with 20 simultaneous persons
    # Each person has 1 person box + 1 helmet box + 1 vest box = 60 detections per frame!
    num_frames = 500
    num_persons = 20

    prebuilt_frames = []
    for f_idx in range(num_frames):
        ts = f_idx * 0.04
        dets = []
        for p in range(num_persons):
            # Spread people across the image
            base_x = 100.0 + (p * 80.0) % 1600.0
            base_y = 400.0 + (p * 15.0) % 400.0
            dets.append(
                Detection(
                    class_name="person",
                    conf=0.9,
                    box=Box(base_x, base_y, base_x + 60.0, base_y + 200.0),
                    track_id=p + 1,
                )
            )
            # Add helmet
            dets.append(
                Detection(
                    class_name="helmet",
                    conf=0.95,
                    box=Box(base_x + 5.0, base_y + 5.0, base_x + 55.0, base_y + 45.0),
                )
            )
            # Add vest
            dets.append(
                Detection(
                    class_name="vest",
                    conf=0.88,
                    box=Box(base_x + 5.0, base_y + 55.0, base_x + 55.0, base_y + 130.0),
                )
            )
        prebuilt_frames.append(
            FrameMeta(
                ts=ts,
                frame_id=f_idx,
                camera_id="cam-01",
                detections=dets,
                frame=FrameDimensions(width=1920, height=1080),
            )
        )

    # Measure CPU process time
    start_time = time.perf_counter()
    for frame in prebuilt_frames:
        engine.process_frame(frame)
    elapsed_s = time.perf_counter() - start_time

    avg_ms_per_frame = (elapsed_s / num_frames) * 1000.0
    effective_fps = num_frames / elapsed_s

    print(
        f"\n[Benchmark] Processed {num_frames} frames ({num_persons} persons each) in {elapsed_s:.3f}s"
    )
    print(f"[Benchmark] Avg time per frame: {avg_ms_per_frame:.2f} ms ({effective_fps:.1f} FPS)")

    # 15% of one CPU core at 25 FPS = 0.15 * 40ms = 6.0 ms per frame
    assert avg_ms_per_frame < 6.0, (
        f"Engine too slow: {avg_ms_per_frame:.2f} ms/frame exceeds 6.0 ms budget"
    )
