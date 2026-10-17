"""Use case for spatial zone hot-reloading and versioned persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Union

from sentinel.domain.zones import ZoneManager


class ManageZonesUseCase:
    """Manages zone definitions, geometric validation, versioning, and atomic configuration updates."""

    def __init__(
        self,
        zone_manager: ZoneManager,
        config_path: Union[str, Path] = "config/zones.json",
    ) -> None:
        self.zone_manager = zone_manager
        self.config_path = Path(config_path)

    def get_zones_dict(self) -> Dict[str, Any]:
        """Returns the current zone configuration as a dictionary."""
        return {
            "frame": {
                "width": self.zone_manager.ref_width,
                "height": self.zone_manager.ref_height,
            },
            "zones": [
                {
                    "id": z.id,
                    "type": z.type,
                    "required_ppe": sorted(list(z.required_ppe)),
                    "polygon": z.raw_coords,
                }
                for z in self.zone_manager.zones
            ],
        }

    def update_zones(self, new_config: Dict[str, Any]) -> Tuple[ZoneManager, Dict[str, Any]]:
        """Validates new zone geometry, writes atomically to config/zones.json, and reloads manager.

        Returns (reloaded_manager, diff_summary).
        """
        # 1. Parse and validate new zones
        new_manager = ZoneManager.from_config_dict(new_config)
        for z in new_manager.zones:
            z.validate_geometry(max_width=new_manager.ref_width, max_height=new_manager.ref_height)

        # 2. Compute diff
        old_ids = {z.id for z in self.zone_manager.zones}
        new_ids = {z.id for z in new_manager.zones}
        diff = {
            "added": sorted(list(new_ids - old_ids)),
            "removed": sorted(list(old_ids - new_ids)),
            "updated": sorted(list(old_ids & new_ids)),
            "total_zones": len(new_manager.zones),
        }

        # 3. Write atomically via temp file
        payload = json.dumps(new_config, indent=2) + "\n"
        temp_file = self.config_path.with_suffix(".tmp")
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(payload, encoding="utf-8")
        temp_file.replace(self.config_path)

        # 4. Hot-reload active manager
        self.zone_manager.zones = new_manager.zones
        self.zone_manager.ref_width = new_manager.ref_width
        self.zone_manager.ref_height = new_manager.ref_height

        return self.zone_manager, diff
