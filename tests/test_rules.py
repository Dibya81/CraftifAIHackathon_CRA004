import pytest

from sentinel.config import FrameDimensions, RulesConfig, ZoneDefinition, ZonesConfig
from sentinel.domain.models import Box, Detection, FrameMeta
from sentinel.domain.rules import RuleEngine
from sentinel.domain.zones import ZoneManager


def make_test_engine(cooldown_s: float = 30.0) -> RuleEngine:
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
    rules_cfg = RulesConfig(cooldown_s=cooldown_s)
    zm = ZoneManager(zones_cfg)
    return RuleEngine(rules_cfg=rules_cfg, zone_manager=zm)


@pytest.mark.tc("TC-12")
def test_ac2_no_helmet_single_incident_within_3s():
    """AC-2: Person without helmet triggers exactly one NO_HELMET incident within 3 s;

    person with helmet triggers none.
    """
    engine = make_test_engine()

    # Track 1: Person without helmet in walkway zone (requires helmet)
    # Simulate 25 FPS (0.04s per frame) for 3.0 seconds (75 frames)
    all_incidents = []
    for f_idx in range(75):
        ts = f_idx * 0.04
        frame = FrameMeta(
            ts=ts,
            frame_id=f_idx,
            camera_id="cam-01",
            detections=[
                # Foot point: (500, 800) -> inside walkway
                Detection(class_name="person", conf=0.92, box=Box(400, 400, 600, 800), track_id=1)
            ],
        )
        incs = engine.process_frame(frame)
        all_incidents.extend(incs)

    # Exactly one incident raised
    assert len(all_incidents) == 1
    inc = all_incidents[0]
    assert inc.type == "NO_HELMET"
    assert inc.track_id == 1
    assert inc.zone == "walkway"
    assert inc.severity == "MEDIUM"
    assert inc.confidence == 0.92
    # Incident raised at debounce threshold 2.0s <= 3.0s
    assert 2.0 <= inc.duration_s <= 2.1


def test_ac2_compliant_person_triggers_no_incident():
    """Person wearing helmet triggers zero incidents."""
    engine = make_test_engine()
    all_incidents = []
    for f_idx in range(75):
        ts = f_idx * 0.04
        frame = FrameMeta(
            ts=ts,
            frame_id=f_idx,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.92, box=Box(400, 400, 600, 800), track_id=2),
                # Helmet on head (top 25% of y=400..800 is 400..500)
                Detection(class_name="helmet", conf=0.95, box=Box(450, 410, 550, 490)),
            ],
        )
        incs = engine.process_frame(frame)
        all_incidents.extend(incs)

    assert len(all_incidents) == 0


@pytest.mark.tc("TC-14")
def test_ac3_zone_intrusion_and_reentry_cooldown():
    """AC-3: Entering a restricted polygon triggers one ZONE_INTRUSION;

    re-entry after cooldown triggers a second.
    """
    engine = make_test_engine(cooldown_s=10.0)

    # Frame 0: Outside restricted zone (safe walkway, foot-point at 500, 800)
    f0 = FrameMeta(
        ts=0.0,
        frame_id=0,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=3),
            Detection(class_name="helmet", conf=0.95, box=Box(450, 410, 550, 490)),
        ],
    )
    assert len(engine.process_frame(f0)) == 0

    # Frame 1 (t=1.0): Person steps into press-area (restricted, foot-point at 1200, 500)
    f1 = FrameMeta(
        ts=1.0,
        frame_id=1,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.91, box=Box(1100, 200, 1300, 500), track_id=3),
            Detection(class_name="helmet", conf=0.95, box=Box(1150, 210, 1250, 270)),
            Detection(class_name="vest", conf=0.90, box=Box(1120, 280, 1280, 400)),
        ],
    )
    incs1 = engine.process_frame(f1)
    assert len(incs1) == 1
    assert incs1[0].type == "ZONE_INTRUSION"
    assert incs1[0].severity == "HIGH"
    assert incs1[0].zone == "press-area"

    # Frame 2-10 (t=1.5..5.0): Staying in restricted zone should NOT re-trigger incident
    for step in range(8):
        f = FrameMeta(
            ts=1.5 + step * 0.5,
            frame_id=2 + step,
            camera_id="cam-01",
            detections=[
                Detection(
                    class_name="person", conf=0.91, box=Box(1100, 200, 1300, 500), track_id=3
                ),
                Detection(class_name="helmet", conf=0.95, box=Box(1150, 210, 1250, 270)),
                Detection(class_name="vest", conf=0.90, box=Box(1120, 280, 1280, 400)),
            ],
        )
        assert len(engine.process_frame(f)) == 0

    # Step outside to walkway at t=6.0
    f_out = FrameMeta(
        ts=6.0,
        frame_id=20,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=3),
            Detection(class_name="helmet", conf=0.95, box=Box(450, 410, 550, 490)),
        ],
    )
    assert len(engine.process_frame(f_out)) == 0

    # Re-entry at t=12.0 (> cooldown 10.0s since t=1.0)
    f_reenter = FrameMeta(
        ts=12.0,
        frame_id=30,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.93, box=Box(1100, 200, 1300, 500), track_id=3),
            Detection(class_name="helmet", conf=0.95, box=Box(1150, 210, 1250, 270)),
            Detection(class_name="vest", conf=0.90, box=Box(1120, 280, 1280, 400)),
        ],
    )
    incs2 = engine.process_frame(f_reenter)
    assert len(incs2) == 1
    assert incs2[0].type == "ZONE_INTRUSION"


@pytest.mark.tc("TC-12")
def test_debounce_edge():
    """Verify violation duration < min_duration_s does not fire, but >= min_duration_s fires."""
    engine = make_test_engine()

    # Frame at t=0.0
    f0 = FrameMeta(
        ts=0.0,
        frame_id=0,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=1)
        ],
    )
    assert len(engine.process_frame(f0)) == 0

    # Frame at t=1.9 (under 2.0s)
    f1 = FrameMeta(
        ts=1.9,
        frame_id=1,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=1)
        ],
    )
    assert len(engine.process_frame(f1)) == 0

    # Frame at t=2.0 (reaches 2.0s) -> fires!
    f2 = FrameMeta(
        ts=2.0,
        frame_id=2,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=1)
        ],
    )
    incs = engine.process_frame(f2)
    assert len(incs) == 1
    assert incs[0].type == "NO_HELMET"


@pytest.mark.tc("TC-15")
def test_danger_dwell_incident():
    """Verify DANGER_DWELL is raised when person stays in danger zone >= dwell_s (5.0s)."""
    engine = make_test_engine()

    # Foot point at (1350, 200) inside crane-drop (danger)
    all_incidents = []
    for step in range(15):
        ts = step * 0.5  # 0.0 to 7.0s
        frame = FrameMeta(
            ts=ts,
            frame_id=step,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.9, box=Box(1300, 100, 1400, 200), track_id=5),
                Detection(class_name="helmet", conf=0.95, box=Box(1320, 105, 1380, 125)),
                Detection(class_name="vest", conf=0.90, box=Box(1310, 130, 1390, 170)),
            ],
        )
        all_incidents.extend(engine.process_frame(frame))

    # Expect: 1 ZONE_INTRUSION on entry (t=0.0) + 1 DANGER_DWELL at t=5.0
    types = [inc.type for inc in all_incidents]
    assert "ZONE_INTRUSION" in types
    assert "DANGER_DWELL" in types
    dwell_inc = next(inc for inc in all_incidents if inc.type == "DANGER_DWELL")
    assert dwell_inc.severity == "HIGH"
    assert dwell_inc.duration_s >= 5.0


def test_track_loss_and_reuse():
    """A track lost for > 2.0s is purged; if ID reappears, it is fresh."""
    engine = make_test_engine()

    # Track 8 lacks helmet for 1.5s (not yet debounced)
    engine.process_frame(
        FrameMeta(
            ts=0.0,
            frame_id=0,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=8)
            ],
        )
    )
    engine.process_frame(
        FrameMeta(
            ts=1.5,
            frame_id=1,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=8)
            ],
        )
    )

    # Track disappears until t=4.0 (> 2s gap from t=1.5)
    f_gap = FrameMeta(
        ts=4.0,
        frame_id=2,
        camera_id="cam-01",
        detections=[
            Detection(class_name="person", conf=0.9, box=Box(400, 400, 600, 800), track_id=8)
        ],
    )
    # The previous 1.5s should NOT carry over to trigger immediately at t=4.0!
    incs = engine.process_frame(f_gap)
    assert len(incs) == 0


def test_deterministic_replay():
    """Identical frame sequence produces identical incidents with identical timestamps and IDs."""
    frames = [
        FrameMeta(
            ts=i * 0.1,
            frame_id=i,
            camera_id="cam-01",
            detections=[
                Detection(class_name="person", conf=0.85, box=Box(400, 400, 600, 800), track_id=10)
            ],
        )
        for i in range(30)
    ]

    engine1 = make_test_engine()
    incs1 = []
    for f in frames:
        incs1.extend(engine1.process_frame(f))

    engine2 = make_test_engine()
    incs2 = []
    for f in frames:
        incs2.extend(engine2.process_frame(f))

    assert len(incs1) == len(incs2) == 1
    assert incs1[0].type == incs2[0].type == "NO_HELMET"
    assert incs1[0].duration_s == incs2[0].duration_s
    assert incs1[0].confidence == incs2[0].confidence
