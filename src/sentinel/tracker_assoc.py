"""Backward-compatible PPE tracker association module."""

from __future__ import annotations

from typing import List, Optional

from sentinel.config import AssociationConfig
from sentinel.domain.association import (
    PersonPPEStatus,
)
from sentinel.domain.association import (
    TrackerPPEAssociator as DomainAssociator,
)
from sentinel.domain.association import (
    associate_ppe as domain_associate_ppe,
)
from sentinel.domain.models import Detection


def associate_ppe(
    persons: List[Detection],
    ppe_detections: List[Detection],
    cfg: AssociationConfig,
) -> List[PersonPPEStatus]:
    """Backward-compatible associate_ppe accepting AssociationConfig."""
    return domain_associate_ppe(
        persons=persons,
        ppe_detections=ppe_detections,
        head_region=cfg.head_region,
        torso_region=cfg.torso_region,
        min_overlap=cfg.min_overlap,
    )


class TrackerPPEAssociator(DomainAssociator):
    """Backward-compatible TrackerPPEAssociator accepting AssociationConfig."""

    def __init__(
        self,
        cfg: Optional[AssociationConfig] = None,
        min_overlap: Optional[float] = None,
    ) -> None:
        c = cfg if cfg is not None else AssociationConfig()
        overlap = min_overlap if min_overlap is not None else c.min_overlap
        super().__init__(
            head_region=c.head_region,
            torso_region=c.torso_region,
            min_overlap=overlap,
        )


__all__ = ["PersonPPEStatus", "TrackerPPEAssociator", "associate_ppe"]
