"""Domain association logic matching PPE detections to tracked persons.

Anatomical Region Rules:
- Head region: top 0-25% of person bounding box. Helmet worn if intersection-over-helmet-area >= min_overlap.
- Torso region: 25-70% of person bounding box. Vest worn if intersection-over-vest-area >= min_overlap.
- Explicit 'no_helmet' detection in head region flags an explicit violation with elevated confidence.
- Greedy bipartite matching: assigns each PPE detection to at most one person (highest overlap).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Set, Tuple

from sentinel.domain.models import Box, Detection


@dataclass
class PersonPPEStatus:
    """PPE association status for a detected person."""

    person: Detection
    has_helmet: bool = False
    has_vest: bool = False
    explicit_no_helmet: bool = False
    helmet_detection: Optional[Detection] = None
    no_helmet_detection: Optional[Detection] = None
    vest_detection: Optional[Detection] = None
    helmet_overlap: float = 0.0
    vest_overlap: float = 0.0
    no_helmet_overlap: float = 0.0

    @property
    def track_id(self) -> Optional[int]:
        return self.person.track_id

    @property
    def box(self) -> Box:
        return self.person.box

    @property
    def person_conf(self) -> float:
        return self.person.conf

    def missing_ppe(self, required: Set[str]) -> Set[str]:
        """Returns the set of required PPE items that are missing for this person."""
        missing = set()
        if "helmet" in required and not self.has_helmet:
            missing.add("helmet")
        if "vest" in required and not self.has_vest:
            missing.add("vest")
        return missing


def associate_ppe(
    persons: List[Detection],
    ppe_detections: List[Detection],
    head_region: Tuple[float, float] = (0.0, 0.25),
    torso_region: Tuple[float, float] = (0.25, 0.70),
    min_overlap: float = 0.20,
) -> List[PersonPPEStatus]:
    """Associates PPE detections to candidate persons using anatomical region overlap."""
    if not persons:
        return []

    statuses = [PersonPPEStatus(person=p) for p in persons]

    helmets = [d for d in ppe_detections if d.class_name == "helmet"]
    no_helmets = [d for d in ppe_detections if d.class_name in {"no_helmet", "head"}]
    vests = [d for d in ppe_detections if d.class_name == "vest"]

    head_top, head_bottom = head_region
    torso_top, torso_bottom = torso_region

    # 1. Match helmets to head region
    _assign_ppe_to_persons(
        persons=persons,
        statuses=statuses,
        ppe_items=helmets,
        region_func=lambda b: b.sub_region(head_top, head_bottom),
        min_overlap=min_overlap,
        assign_func=_assign_helmet,
    )

    # 2. Match explicit no_helmet detections to head region
    _assign_ppe_to_persons(
        persons=persons,
        statuses=statuses,
        ppe_items=no_helmets,
        region_func=lambda b: b.sub_region(head_top, head_bottom),
        min_overlap=min_overlap,
        assign_func=_assign_no_helmet,
    )

    # If explicit no_helmet is present with strong overlap, it overrides helmet detection
    for st in statuses:
        if st.explicit_no_helmet and st.no_helmet_overlap > st.helmet_overlap:
            st.has_helmet = False

    # 3. Match vests to torso region
    _assign_ppe_to_persons(
        persons=persons,
        statuses=statuses,
        ppe_items=vests,
        region_func=lambda b: b.sub_region(torso_top, torso_bottom),
        min_overlap=min_overlap,
        assign_func=_assign_vest,
    )

    return statuses


def _assign_ppe_to_persons(
    persons: List[Detection],
    statuses: List[PersonPPEStatus],
    ppe_items: List[Detection],
    region_func: Callable[[Box], Box],
    min_overlap: float,
    assign_func: Callable[[PersonPPEStatus, Detection, float], None],
) -> None:
    """Greedy bipartite matching: assigns each PPE item to the best-matching person."""
    if not ppe_items:
        return

    candidates: List[Tuple[float, int, int]] = []
    for p_idx, person in enumerate(persons):
        region_box = region_func(person.box)
        for i_idx, item in enumerate(ppe_items):
            overlap = region_box.intersection_over_other(item.box)
            if overlap >= min_overlap:
                candidates.append((overlap, p_idx, i_idx))

    # Sort descending by overlap score so best matches claim their items first
    candidates.sort(key=lambda x: x[0], reverse=True)

    matched_persons: Set[int] = set()
    matched_items: Set[int] = set()

    for overlap, p_idx, i_idx in candidates:
        if p_idx in matched_persons or i_idx in matched_items:
            continue
        assign_func(statuses[p_idx], ppe_items[i_idx], overlap)
        matched_persons.add(p_idx)
        matched_items.add(i_idx)


def _assign_helmet(status: PersonPPEStatus, item: Detection, overlap: float) -> None:
    status.has_helmet = True
    status.helmet_detection = item
    status.helmet_overlap = overlap


def _assign_no_helmet(status: PersonPPEStatus, item: Detection, overlap: float) -> None:
    status.explicit_no_helmet = True
    status.no_helmet_detection = item
    status.no_helmet_overlap = overlap


def _assign_vest(status: PersonPPEStatus, item: Detection, overlap: float) -> None:
    status.has_vest = True
    status.vest_detection = item
    status.vest_overlap = overlap


class TrackerPPEAssociator:
    """Convenience class wrapper around associate_ppe for frame processing pipelines."""

    def __init__(
        self,
        head_region: Tuple[float, float] = (0.0, 0.25),
        torso_region: Tuple[float, float] = (0.25, 0.70),
        min_overlap: float = 0.20,
    ) -> None:
        self.head_region = head_region
        self.torso_region = torso_region
        self.min_overlap = min_overlap

    def associate(self, meta: Any, detections: List[Detection]) -> List[PersonPPEStatus]:
        persons = [d for d in detections if d.class_name == "person"]
        ppe = [d for d in detections if d.class_name in {"helmet", "no_helmet", "head", "vest"}]
        return associate_ppe(
            persons=persons,
            ppe_detections=ppe,
            head_region=self.head_region,
            torso_region=self.torso_region,
            min_overlap=self.min_overlap,
        )
