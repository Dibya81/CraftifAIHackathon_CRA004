"""Polygon zone geometry (shapely). Foot-point of a person box is tested against zones.

Supports polygon zones (safe, restricted, danger), required PPE per zone, and
automatic coordinate rescaling between runtime detection frame sizes and configured zone sizes.
Domain logic rules:
- At least 3 points, no self-intersection, inside frame.
- Foot-point test (bottom center of box).
- Rescale when frame size differs.
- Overlapping zones resolved by precedence: danger > restricted > safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from shapely.geometry import Point, Polygon

from sentinel.domain.models import Box


class InvalidZoneError(ValueError):
    """Raised when a zone definition violates geometric or schema invariants."""

    pass


@dataclass
class Zone:
    """A spatial safety zone with an ID, type, required PPE, and polygon geometry."""

    id: str
    type: str  # safe | restricted | danger
    required_ppe: Set[str] = field(default_factory=set)
    polygon: Polygon = field(default_factory=lambda: Polygon())
    raw_coords: List[List[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.raw_coords) >= 3 and self.polygon.is_empty:
            self.polygon = Polygon(self.raw_coords)
        if not self.polygon.is_valid:
            self.polygon = self.polygon.buffer(0)

    def contains_point(self, pt: Tuple[float, float]) -> bool:
        """Check if point (x, y) is inside or on the boundary of the zone polygon."""
        p = Point(pt[0], pt[1])
        return bool(self.polygon.covers(p) or self.polygon.contains(p))

    def validate_geometry(self, max_width: int = 1920, max_height: int = 1080) -> None:
        """Validates polygon satisfies >= 3 points, non-empty, and coordinates within bounds."""
        if len(self.raw_coords) < 3:
            raise InvalidZoneError(
                f"Zone '{self.id}' must have at least 3 vertices, got {len(self.raw_coords)}"
            )
        poly = Polygon(self.raw_coords)
        if poly.is_empty or poly.area <= 0:
            raise InvalidZoneError(f"Zone '{self.id}' polygon has zero or invalid area")
        for x, y in self.raw_coords:
            if x < 0 or x > max_width * 2 or y < 0 or y > max_height * 2:
                raise InvalidZoneError(
                    f"Zone '{self.id}' vertex ({x}, {y}) out of expected frame bounds"
                )


class ZoneManager:
    """Manages loaded zones and evaluates spatial presence against detection frames."""

    # Priority order when a point falls into multiple overlapping zones
    PRIORITY: Dict[str, int] = {"danger": 3, "restricted": 2, "safe": 1}

    def __init__(
        self,
        config_or_zones: Union[Any, List[Zone]],
        ref_width: int = 1920,
        ref_height: int = 1080,
    ) -> None:
        # Check if passed a ZonesConfig object
        if hasattr(config_or_zones, "zones") and hasattr(config_or_zones, "frame"):
            cfg = config_or_zones
            self.ref_width = cfg.frame.width
            self.ref_height = cfg.frame.height
            self.zones = []
            for zd in cfg.zones:
                coords = zd.polygon
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                self.zones.append(
                    Zone(
                        id=zd.id,
                        type=zd.type,
                        required_ppe=set(zd.required_ppe),
                        polygon=poly,
                        raw_coords=coords,
                    )
                )
        elif isinstance(config_or_zones, list):
            self.zones = config_or_zones
            self.ref_width = ref_width
            self.ref_height = ref_height
        else:
            self.zones = []
            self.ref_width = ref_width
            self.ref_height = ref_height

    @classmethod
    def from_config_dict(cls, data: Dict[str, Any]) -> ZoneManager:
        frame_dict = data.get("frame", {"width": 1920, "height": 1080})
        ref_w = frame_dict.get("width", 1920)
        ref_h = frame_dict.get("height", 1080)
        zones_list: List[Zone] = []
        for zd in data.get("zones", []):
            coords = zd.get("polygon", [])
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            z = Zone(
                id=zd["id"],
                type=zd.get("type", "safe"),
                required_ppe=set(zd.get("required_ppe", [])),
                polygon=poly,
                raw_coords=coords,
            )
            zones_list.append(z)
        return cls(zones_list, ref_width=ref_w, ref_height=ref_h)

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
        """Finds highest-priority zone covering the person's foot-point."""
        matched = self.find_zones_for_point(person_box.foot_point, frame_width, frame_height)
        return matched[0] if matched else None

    def match_box(
        self,
        box: Box,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> Optional[Zone]:
        """Matches a bounding box to its primary zone by testing its foot-point."""
        return self.find_best_zone_for_person(box, frame_width, frame_height)

    def get_required_ppe_for_person(
        self,
        person_box: Box,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        default_ppe: Optional[Set[str]] = None,
    ) -> Set[str]:
        """Returns the set of required PPE items for the person's current zone."""
        zone = self.find_best_zone_for_person(person_box, frame_width, frame_height)
        if zone is not None:
            return zone.required_ppe
        return default_ppe if default_ppe is not None else set()
