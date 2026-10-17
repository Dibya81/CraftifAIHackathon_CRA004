"""Unit tests for spatial zones and frame coordinate rescaling."""
from sentinel.config import FrameDimensions, ZoneDefinition, ZonesConfig
from sentinel.models import Box
from sentinel.zones import ZoneManager


def make_test_manager():
    cfg = ZonesConfig(
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
    return ZoneManager(cfg)


def test_foot_point_zone_matching():
    zm = make_test_manager()

    # Person with foot-point at (500, 800) -> inside walkway (safe)
    person_box = Box(400, 400, 600, 800)
    zone = zm.find_best_zone_for_person(person_box)
    assert zone is not None
    assert zone.id == "walkway"
    assert zone.type == "safe"
    assert zone.required_ppe == {"helmet"}

    # Person with foot-point at (1200, 500) -> inside press-area (restricted)
    person_box2 = Box(1100, 200, 1300, 500)
    zone2 = zm.find_best_zone_for_person(person_box2)
    assert zone2 is not None
    assert zone2.id == "press-area"
    assert zone2.type == "restricted"
    assert zone2.required_ppe == {"helmet", "vest"}


def test_zone_boundary_points():
    zm = make_test_manager()
    # Exactly on boundary point [100, 600]
    person_box = Box(50, 400, 150, 600)  # foot_point is (100, 600)
    zone = zm.find_best_zone_for_person(person_box)
    assert zone is not None
    assert zone.id == "walkway"


def test_coordinate_rescaling_different_frame_size():
    zm = make_test_manager()  # Reference frame is 1920x1080

    # Incoming detections are from 1280x720 video
    # A point at (500 * 1280 / 1920, 800 * 720 / 1080) = (333.33, 533.33)
    scale_x = 1280 / 1920
    scale_y = 720 / 1080
    person_box_720p = Box(
        x1=400 * scale_x,
        y1=400 * scale_y,
        x2=600 * scale_x,
        y2=800 * scale_y,
    )
    zone = zm.find_best_zone_for_person(person_box_720p, frame_width=1280, frame_height=720)
    assert zone is not None
    assert zone.id == "walkway"


def test_overlapping_priority():
    # Danger zone has priority over restricted zone
    cfg = ZonesConfig(
        frame=FrameDimensions(width=1000, height=1000),
        zones=[
            ZoneDefinition(
                id="restricted-big",
                type="restricted",
                required_ppe=["helmet"],
                polygon=[[0, 0], [1000, 0], [1000, 1000], [0, 1000]],
            ),
            ZoneDefinition(
                id="danger-inner",
                type="danger",
                required_ppe=["helmet", "vest"],
                polygon=[[200, 200], [600, 200], [600, 600], [200, 600]],
            ),
        ],
    )
    zm = ZoneManager(cfg)
    # Foot-point at (400, 400) falls in both
    b = Box(300, 100, 500, 400)
    zone = zm.find_best_zone_for_person(b)
    assert zone is not None
    assert zone.id == "danger-inner"
    assert zone.type == "danger"


def test_zone_manager_from_file_and_getters():
    zm = ZoneManager.from_file("config/zones.json")
    z = zm.get_zone_by_id("walkway")
    assert z is not None
    assert z.type == "safe"
    assert zm.get_zone_by_id("non-existent") is None

    # Test required PPE helper
    b = Box(400, 400, 600, 800)  # in walkway
    ppe = zm.get_required_ppe_for_person(b)
    assert ppe == {"helmet"}

    # Outside all zones
    b_outside = Box(10, 10, 20, 20)
    ppe_outside = zm.get_required_ppe_for_person(b_outside, default_ppe={"helmet"})
    assert ppe_outside == {"helmet"}

