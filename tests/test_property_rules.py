"""Property-based tests for pure domain rule engine using Hypothesis."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sentinel.config import RulesConfig
from sentinel.domain.models import Box, Detection, FrameMeta
from sentinel.domain.rules import EngineState, step
from sentinel.domain.zones import Zone, ZoneManager


def make_test_zone_manager() -> ZoneManager:
    zones = [
        Zone(
            id="work-area",
            type="restricted",
            required_ppe={"helmet", "vest"},
            raw_coords=[[0.0, 0.0], [1000.0, 0.0], [1000.0, 1000.0], [0.0, 1000.0]],
        )
    ]
    return ZoneManager(zones, ref_width=1000, ref_height=1000)


@pytest.mark.tc("TC-12")
@given(
    track_id=st.integers(min_value=1, max_value=100),
    num_frames=st.integers(min_value=1, max_value=15),
    delta_t=st.floats(min_value=0.01, max_value=0.10),
)
@settings(max_examples=30)
def test_property_no_incident_before_min_duration(track_id: int, num_frames: int, delta_t: float):
    """Invariant: No incident is ever raised before min_duration_s has elapsed."""
    zm = make_test_zone_manager()
    rules_cfg = RulesConfig()
    rules_cfg.no_helmet.min_duration_s = 2.0

    state = EngineState()
    all_incidents = []

    for i in range(num_frames):
        ts = i * delta_t
        if ts >= rules_cfg.no_helmet.min_duration_s:
            break
        frame = FrameMeta(
            ts=ts,
            frame_id=i,
            camera_id="cam-01",
            detections=[
                Detection(
                    class_name="person", conf=0.9, box=Box(100, 100, 200, 300), track_id=track_id
                )
            ],
        )
        state, incs = step(state, frame, zm, rules_cfg)
        all_incidents.extend(incs)

    # Check debounced PPE incidents (ZONE_INTRUSION is zero-delay by design upon entry)
    debounced_incs = [inc for inc in all_incidents if inc.type in {"NO_HELMET", "NO_VEST"}]
    assert len(debounced_incs) == 0, (
        f"Expected 0 debounced PPE incidents before 2.0s, got {len(debounced_incs)}"
    )


@pytest.mark.tc("TC-13")
@given(
    track_id=st.integers(min_value=1, max_value=100),
    total_duration_s=st.floats(min_value=2.5, max_value=10.0),
)
@settings(max_examples=25)
def test_property_at_most_one_incident_per_track_without_cooldown(
    track_id: int, total_duration_s: float
):
    """Invariant: At most one continuous incident per track is raised within cooldown window."""
    zm = make_test_zone_manager()
    rules_cfg = RulesConfig()
    rules_cfg.no_helmet.min_duration_s = 1.0
    rules_cfg.cooldown_s = 30.0  # long cooldown

    state = EngineState()
    all_incidents = []

    steps = int(total_duration_s / 0.1)
    for i in range(steps):
        ts = i * 0.1
        frame = FrameMeta(
            ts=ts,
            frame_id=i,
            camera_id="cam-01",
            detections=[
                Detection(
                    class_name="person", conf=0.9, box=Box(100, 100, 200, 300), track_id=track_id
                )
            ],
        )
        state, incs = step(state, frame, zm, rules_cfg)
        all_incidents.extend(incs)

    # Filter to NO_HELMET
    no_helmet_incs = [inc for inc in all_incidents if inc.type == "NO_HELMET"]
    assert len(no_helmet_incs) <= 1, (
        f"Expected <= 1 NO_HELMET incident within cooldown, got {len(no_helmet_incs)}"
    )


@pytest.mark.tc("TC-12")
@given(
    track_ids=st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=5, unique=True)
)
@settings(max_examples=20)
def test_property_replay_determinism(track_ids: list[int]):
    """Invariant: Same frames into step() yield identical states and incidents."""
    zm = make_test_zone_manager()
    rules_cfg = RulesConfig()
    rules_cfg.no_helmet.min_duration_s = 0.5

    frames = []
    for i in range(10):
        dets = [
            Detection(
                class_name="person",
                conf=0.9,
                box=Box(50 * tid, 50 * tid, 50 * tid + 50, 50 * tid + 100),
                track_id=tid,
            )
            for tid in track_ids
        ]
        frames.append(FrameMeta(ts=i * 0.1, frame_id=i, camera_id="cam-01", detections=dets))

    # Run 1
    state1 = EngineState()
    incs1 = []
    for f in frames:
        state1, r_incs = step(state1, f, zm, rules_cfg)
        incs1.extend(r_incs)

    # Run 2
    state2 = EngineState()
    incs2 = []
    for f in frames:
        state2, r_incs = step(state2, f, zm, rules_cfg)
        incs2.extend(r_incs)

    assert len(incs1) == len(incs2)
    for a, b in zip(incs1, incs2):
        assert a.type == b.type
        assert a.track_id == b.track_id
        assert a.duration_s == b.duration_s
        assert a.confidence == b.confidence
    assert state1.tracks.keys() == state2.tracks.keys()
