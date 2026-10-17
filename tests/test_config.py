"""Tests for config loading and validation error formatting."""
from pathlib import Path

import pytest

from sentinel.config import (
    ConfigurationError,
    RulesConfig,
    SentinelConfig,
    ZonesConfig,
    load_rules_config,
    load_sentinel_config,
    load_zones_config,
)


def test_load_default_sentinel_config():
    cfg = load_sentinel_config("config/sentinel.yaml")
    assert isinstance(cfg, SentinelConfig)
    assert cfg.camera_id == "cam-01"
    assert cfg.privacy.require_blurred_source is True
    assert cfg.mqtt.port == 1883
    assert "person" in cfg.class_map


def test_load_default_rules_config():
    cfg = load_rules_config("config/rules.yaml")
    assert isinstance(cfg, RulesConfig)
    assert cfg.no_helmet.enabled is True
    assert cfg.no_helmet.min_duration_s == 2.0
    assert cfg.danger_dwell.dwell_s == 5.0
    assert cfg.cooldown_s == 30.0
    assert cfg.association.min_overlap == 0.3


def test_load_default_zones_config():
    cfg = load_zones_config("config/zones.json")
    assert isinstance(cfg, ZonesConfig)
    assert cfg.frame.width == 1920
    assert cfg.frame.height == 1080
    assert len(cfg.zones) >= 3
    zone_ids = [z.id for z in cfg.zones]
    assert "walkway" in zone_ids
    assert "press-area" in zone_ids
    assert "crane-drop" in zone_ids


def test_missing_config_raises_actionable_error(tmp_path: Path):
    with pytest.raises(ConfigurationError) as exc_info:
        load_sentinel_config(tmp_path / "nonexistent.yaml")
    assert "not found" in str(exc_info.value)


def test_invalid_yaml_field_raises_clear_error(tmp_path: Path):
    bad_yaml = tmp_path / "bad_rules.yaml"
    bad_yaml.write_text("cooldown_s: -10\n", encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc_info:
        load_rules_config(bad_yaml)
    assert "cooldown_s" in str(exc_info.value)


def test_invalid_polygon_raises_clear_error(tmp_path: Path):
    bad_zones = tmp_path / "bad_zones.json"
    bad_zones.write_text(
        '{"frame": {"width": 100, "height": 100}, "zones": [{"id": "z1", "type": "safe", "polygon": [[1,2]]}]}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_zones_config(bad_zones)
    assert "Polygon must have at least 3 vertices" in str(exc_info.value)
