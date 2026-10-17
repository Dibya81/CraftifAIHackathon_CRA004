"""Unit tests for Box geometry, Detection, FrameMeta, and Incident."""
from sentinel.models import Box, Incident


def test_box_properties():
    b = Box(100.0, 200.0, 300.0, 600.0)
    assert b.width == 200.0
    assert b.height == 400.0
    assert b.area == 80000.0
    assert b.foot_point == (200.0, 600.0)


def test_box_inverted_coordinates_fixed():
    b = Box(300.0, 600.0, 100.0, 200.0)
    assert b.x1 == 100.0
    assert b.x2 == 300.0
    assert b.y1 == 200.0
    assert b.y2 == 600.0


def test_box_sub_region():
    b = Box(100.0, 200.0, 300.0, 600.0)  # height = 400
    head = b.sub_region(0.0, 0.25)
    assert head.x1 == 100.0
    assert head.x2 == 300.0
    assert head.y1 == 200.0
    assert head.y2 == 300.0  # 200 + 0.25*400

    torso = b.sub_region(0.25, 0.70)
    assert torso.y1 == 300.0
    assert torso.y2 == 480.0  # 200 + 0.70*400


def test_box_intersections():
    b1 = Box(0.0, 0.0, 100.0, 100.0)
    b2 = Box(50.0, 0.0, 150.0, 100.0)
    assert b1.intersection_area(b2) == 5000.0
    # Overlap with respect to b2 area (10000)
    assert b1.intersection_over_other(b2) == 0.5


def test_incident_create_and_serialize():
    inc = Incident.create(
        incident_type="NO_HELMET",
        severity="MEDIUM",
        track_id=7,
        camera_id="cam-01",
        confidence=0.8876,
        duration_s=2.345,
        zone="press-area",
    )
    assert inc.incident_id is not None
    assert inc.confidence == 0.888
    assert inc.duration_s == 2.35
    data = inc.to_dict()
    assert data["type"] == "NO_HELMET"
    assert data["track_id"] == 7
    assert data["zone"] == "press-area"
