"""Polygon zone geometry (shapely). Foot-point of a person box is tested against zones.

Supports polygon zones (safe, restricted, danger), required PPE per zone, and
automatic coordinate rescaling between runtime detection frame sizes and configured zone sizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple, Union

from shapely.geometry import Point, Polygon

from sentinel.config import ZonesConfig, load_zones_config
from sentinel.models import Box


@dataclass
class Zone:
    """A spatial safety zone with an ID, type, required PPE, and polygon geometry."""

    id: str
    type: str  # safe | restricted | danger
    required_ppe: Set[str] = field(default_factory=set)
    polygon: Polygon = field(default_factory=lambda: Polygon())
    raw_coords: List[List[float]] = field(default_factory=list)

    def contains_point(self, pt: Tuple[float, float]) -> bool:
        """Check if point (x, y) is inside or on the boundary of the zone polygon."""
        p = Point(pt[0], pt[1])
        # covers includes the boundary points
        return self.polygon.covers(p) or self.polygon.contains(p)


class ZoneManager:
    """Manages loaded zones and evaluates spatial presence against detection frames."""

    # Priority order when a point falls into multiple overlapping zones
    PRIORITY = {"danger": 3, "restricted": 2, "safe": 1}

    def __init__(self, config: ZonesConfig) -> None:
        self.ref_width: int = config.frame.width
        self.ref_height: int = config.frame.height
        self.zones: List[Zone] = []
        for zd in config.zones:
            poly = Polygon(zd.polygon)
            # Ensure valid geometry
            if not poly.is_valid:
                poly = poly.buffer(0)
            self.zones.append(
                Zone(
                    id=zd.id,
                    type=zd.type,
                    required_ppe=set(zd.required_ppe),
                    polygon=poly,
                    raw_coords=zd.polygon,
                )
            )

    @classmethod
    def from_file(cls, path: Union[str, Path] = "config/zones.json") -> ZoneManager:
        cfg = load_zones_config(path)
        return cls(cfg)

    def get_zone_by_id(self, zone_id: str) -> Optional[Zone]:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def _normalize_point(
        self,
        pt: Tuple[float, float],
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> Tuple[float, float]:
        """Rescales a coordinate from current frame size to reference zone size if sizes differ."""
        if frame_width is None or frame_height is None:
            return pt
        if frame_width <= 0 or frame_height <= 0:
            return pt
        if frame_width == self.ref_width and frame_height == self.ref_height:
            return pt

        scale_x = self.ref_width / float(frame_width)
        scale_y = self.ref_height / float(frame_height)
        return (pt[0] * scale_x, pt[1] * scale_y)

    def find_zones_for_point(
        self,
        pt: Tuple[float, float],
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> List[Zone]:
        """Find all zones covering the given point, taking frame scaling into account."""
        norm_pt = self._normalize_point(pt, frame_width, frame_height)
        matched = [z for z in self.zones if z.contains_point(norm_pt)]
        # Sort by priority (danger > restricted > safe)
        matched.sort(key=lambda z: self.PRIORITY.get(z.type, 0), reverse=True)
        return matched

    def find_best_zone_for_person(
        self,
        person_box: Box,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> Optional[Zone]:
        """Tests the foot-point (bottom-center of bounding box) against all zones."""
        foot_pt = person_box.foot_point
        matched = self.find_zones_for_point(foot_pt, frame_width, frame_height)
        return matched[0] if matched else None

    def get_required_ppe_for_person(
        self,
        person_box: Box,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        default_ppe: Optional[Set[str]] = None,
    ) -> Set[str]:
        """Returns the set of required PPE for the zone the person is standing in."""
        zone = self.find_best_zone_for_person(person_box, frame_width, frame_height)
        if zone is not None:
            return zone.required_ppe
        return default_ppe if default_ppe is not None else set()
