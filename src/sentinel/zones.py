"""Spatial zones module for SiteSentinel.

Re-exports domain Zone and ZoneManager, providing backward-compatible configuration loading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from sentinel.config import load_zones_config
from sentinel.domain.zones import InvalidZoneError, Zone
from sentinel.domain.zones import ZoneManager as DomainZoneManager


class ZoneManager(DomainZoneManager):
    """Backward-compatible ZoneManager with file loading convenience method."""

    @classmethod
    def from_file(cls, path: Union[str, Path] = "config/zones.json") -> ZoneManager:
        cfg = load_zones_config(path)
        return cls(cfg)


__all__ = ["Zone", "ZoneManager", "InvalidZoneError"]
