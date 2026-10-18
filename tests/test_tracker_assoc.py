import pytest

from sentinel.config import AssociationConfig
from sentinel.domain.association import associate_ppe
from sentinel.domain.models import Box, Detection


@pytest.mark.tc("TC-09")
def test_basic_helmet_and_vest_association():
    cfg = AssociationConfig(head_region=(0.0, 0.25), torso_region=(0.25, 0.70), min_overlap=0.3)

    # Person from y=100 to y=500 (height 400).
    # Head region: y=100 to 200. Torso region: y=200 to 380.
    person = Detection(class_name="person", conf=0.9, box=Box(100, 100, 200, 500), track_id=1)
    # Helmet box fully inside head region
    helmet = Detection(class_name="helmet", conf=0.95, box=Box(120, 110, 180, 170))
    # Vest box inside torso region
    vest = Detection(class_name="vest", conf=0.88, box=Box(110, 220, 190, 350))

    statuses = associate_ppe([person], [helmet, vest], cfg)
    assert len(statuses) == 1
    st = statuses[0]
    assert st.has_helmet is True
    assert st.has_vest is True
    assert st.explicit_no_helmet is False
    assert st.helmet_overlap > 0.9
    assert st.vest_overlap > 0.9


@pytest.mark.tc("TC-11")
def test_explicit_no_helmet_detection():
    cfg = AssociationConfig(head_region=(0.0, 0.25), torso_region=(0.25, 0.70), min_overlap=0.3)
    person = Detection(class_name="person", conf=0.9, box=Box(100, 100, 200, 500), track_id=2)
    # Explicit head without hat in head region
    no_helmet = Detection(class_name="no_helmet", conf=0.94, box=Box(120, 110, 180, 170))

    statuses = associate_ppe([person], [no_helmet], cfg)
    assert len(statuses) == 1
    st = statuses[0]
    assert st.has_helmet is False
    assert st.explicit_no_helmet is True
    assert st.no_helmet_detection is not None
    assert st.no_helmet_detection.conf == 0.94


@pytest.mark.tc("TC-10")
def test_overlapping_persons_claim_best_match():
    cfg = AssociationConfig(head_region=(0.0, 0.25), torso_region=(0.25, 0.70), min_overlap=0.3)

    # Two persons standing very close
    p1 = Detection(class_name="person", conf=0.9, box=Box(100, 100, 200, 500), track_id=10)
    p2 = Detection(class_name="person", conf=0.9, box=Box(150, 100, 250, 500), track_id=20)

    # A helmet centered on p1 (x=110..170) overlaps p1 significantly more than p2
    helmet = Detection(class_name="helmet", conf=0.95, box=Box(110, 110, 170, 170))

    statuses = associate_ppe([p1, p2], [helmet], cfg)
    s1 = next(s for s in statuses if s.track_id == 10)
    s2 = next(s for s in statuses if s.track_id == 20)

    assert s1.has_helmet is True
    # p2 must NOT be assigned the same helmet
    assert s2.has_helmet is False


def test_min_overlap_threshold():
    cfg = AssociationConfig(head_region=(0.0, 0.25), torso_region=(0.25, 0.70), min_overlap=0.3)
    person = Detection(class_name="person", conf=0.9, box=Box(100, 100, 200, 500), track_id=1)
    # Helmet box mostly outside head region (e.g. overlap < 0.3)
    helmet_barely = Detection(class_name="helmet", conf=0.95, box=Box(100, 50, 200, 120))
    # Area of helmet: 100 * 70 = 7000. Overlap with head (100..200): y from 100 to 120 -> 100 * 20 = 2000.
    # IoA = 2000 / 7000 = 0.285 (< 0.3)

    statuses = associate_ppe([person], [helmet_barely], cfg)
    assert len(statuses) == 1
    assert statuses[0].has_helmet is False
