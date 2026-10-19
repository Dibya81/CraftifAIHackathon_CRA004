"""Load and validate sentinel.yaml, rules.yaml and zones.json into typed objects.

Provides explicit, actionable error messages indicating exactly what file, field,
and value failed validation.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class ConfigurationError(Exception):
    """Raised when configuration file parsing or validation fails with an actionable message."""

    pass


# ---------------------------------------------------------------------------
# Sentinel Configuration (config/sentinel.yaml)
# ---------------------------------------------------------------------------


class SourceConfig(BaseModel):
    type: Literal["mqtt", "json_file"] = "mqtt"
    json_file_path: Optional[str] = None

    @model_validator(mode="after")
    def validate_source(self) -> "SourceConfig":
        if self.type == "json_file" and not self.json_file_path:
            raise ValueError(
                "When source.type is 'json_file', source.json_file_path must be specified."
            )
        return self


class MqttConfig(BaseModel):
    host: str = "localhost"
    port: int = Field(default=1883, ge=1, le=65535)
    detections_topic: str = "sentinel/detections"
    incidents_topic: str = "sentinel/incidents"
    health_topic: str = "sentinel/health"


class PathsConfig(BaseModel):
    incidents_log: str = "logs/incidents.jsonl"
    evidence_dir: str = "evidence"
    zones: str = "config/zones.json"


class PrivacyConfig(BaseModel):
    require_blurred_source: bool = True


class EvidenceConfig(BaseModel):
    pre_seconds: int = Field(default=5, ge=1, le=60)
    post_seconds: int = Field(default=5, ge=1, le=60)


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


class AdapterConfig(BaseModel):
    format: Literal["auto", "canonical", "deepstream_pipe", "deepstream_array", "ndjson"] = "auto"
    bbox_format: Literal["xyxy", "xywh"] = "xyxy"
    bbox_normalized: bool = False
    timestamp_format: Literal["epoch", "iso", "pts_fps"] = "epoch"
    fps: float = Field(default=25.0, gt=0.0)
    track_id_fields: List[str] = Field(
        default_factory=lambda: ["track_id", "id", "object_id", "objectId"]
    )
    class_fields: List[str] = Field(
        default_factory=lambda: ["class", "type", "label", "class_id", "classId"]
    )
    conf_fields: List[str] = Field(default_factory=lambda: ["conf", "confidence", "score"])
    bbox_fields: List[str] = Field(default_factory=lambda: ["bbox", "box", "rect"])


class SentinelConfig(BaseModel):
    camera_id: str = "cam-01"
    source: SourceConfig = Field(default_factory=SourceConfig)
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    class_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "person": "person",
            "0": "person",
            "helmet": "helmet",
            "hard_hat": "helmet",
            "1": "helmet",
            "no_helmet": "no_helmet",
            "head": "no_helmet",
            "2": "no_helmet",
            "vest": "vest",
            "safety_vest": "vest",
            "high_vis_vest": "vest",
            "3": "vest",
        }
    )


# ---------------------------------------------------------------------------
# Rules Configuration (config/rules.yaml)
# ---------------------------------------------------------------------------

SeverityType = Literal["LOW", "MEDIUM", "HIGH"]


class RuleConditionConfig(BaseModel):
    enabled: bool = True
    min_duration_s: float = Field(default=2.0, ge=0.0)
    severity: SeverityType = "MEDIUM"


class ZoneIntrusionConfig(BaseModel):
    enabled: bool = True
    severity: SeverityType = "HIGH"


class DangerDwellConfig(BaseModel):
    enabled: bool = True
    dwell_s: float = Field(default=5.0, gt=0.0)
    severity: SeverityType = "HIGH"


class AssociationConfig(BaseModel):
    head_region: Tuple[float, float] = (0.0, 0.25)
    torso_region: Tuple[float, float] = (0.25, 0.70)
    min_overlap: float = Field(default=0.3, ge=0.0, le=1.0)

    @field_validator("head_region", "torso_region")
    @classmethod
    def validate_region(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        if len(v) != 2 or not (0.0 <= v[0] < v[1] <= 1.0):
            raise ValueError(f"Region must be [top, bottom] fractions between 0.0 and 1.0, got {v}")
        return v


class RulesConfig(BaseModel):
    no_helmet: RuleConditionConfig = Field(
        default_factory=lambda: RuleConditionConfig(severity="MEDIUM")
    )
    no_vest: RuleConditionConfig = Field(
        default_factory=lambda: RuleConditionConfig(severity="LOW")
    )
    zone_intrusion: ZoneIntrusionConfig = Field(default_factory=ZoneIntrusionConfig)
    danger_dwell: DangerDwellConfig = Field(default_factory=DangerDwellConfig)
    cooldown_s: float = Field(default=30.0, ge=0.0)
    association: AssociationConfig = Field(default_factory=AssociationConfig)


# ---------------------------------------------------------------------------
# Zones Configuration (config/zones.json)
# ---------------------------------------------------------------------------


class FrameDimensions(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


ZoneType = Literal["safe", "restricted", "danger"]


class ZoneDefinition(BaseModel):
    id: str
    type: ZoneType
    required_ppe: List[str] = Field(default_factory=list)
    polygon: List[List[float]]

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: List[List[float]]) -> List[List[float]]:
        if len(v) < 3:
            raise ValueError(f"Polygon must have at least 3 vertices, got {len(v)}")
        for pt in v:
            if len(pt) != 2:
                raise ValueError(f"Each polygon point must be [x, y], got {pt}")
        return v


class ZonesConfig(BaseModel):
    frame: FrameDimensions
    zones: List[ZoneDefinition]


# ---------------------------------------------------------------------------
# Loading Helpers
# ---------------------------------------------------------------------------


def _format_validation_error(filename: str, exc: ValidationError) -> ConfigurationError:
    messages = []
    for err in exc.errors():
        loc = " -> ".join(str(p) for p in err.get("loc", []))
        msg = err.get("msg", "invalid")
        val = err.get("input", None)
        messages.append(f"  - Field '{loc}': {msg} (received: {val!r})")
    formatted = (
        f"Configuration error in '{filename}':\n"
        + "\n".join(messages)
        + f"\nPlease check '{filename}' and correct the invalid values."
    )
    return ConfigurationError(formatted)


def load_sentinel_config(path: Union[str, Path] = "config/sentinel.yaml") -> SentinelConfig:
    p = Path(path)
    if not p.is_file():
        raise ConfigurationError(
            f"Sentinel config file not found: '{path}'. Please create it or verify path."
        )
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise ConfigurationError(f"YAML syntax error in '{path}': {e}") from e
    try:
        return SentinelConfig.model_validate(data)
    except ValidationError as e:
        raise _format_validation_error(str(path), e) from e


def load_rules_config(path: Union[str, Path] = "config/rules.yaml") -> RulesConfig:
    p = Path(path)
    if not p.is_file():
        raise ConfigurationError(
            f"Rules config file not found: '{path}'. Please create it or verify path."
        )
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise ConfigurationError(f"YAML syntax error in '{path}': {e}") from e
    try:
        return RulesConfig.model_validate(data)
    except ValidationError as e:
        raise _format_validation_error(str(path), e) from e


def load_zones_config(path: Union[str, Path] = "config/zones.json") -> ZonesConfig:
    p = Path(path)
    if not p.is_file():
        raise ConfigurationError(
            f"Zones config file not found: '{path}'. Please create it or verify path."
        )
    try:
        import json

        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigurationError(f"JSON syntax error in '{path}': {e}") from e
    try:
        return ZonesConfig.model_validate(data)
    except ValidationError as e:
        raise _format_validation_error(str(path), e) from e


# Backward compatibility helpers
def load_yaml(path: str) -> Dict[str, Any]:
    res = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return cast(Dict[str, Any], res if isinstance(res, dict) else {})


def load_zones(path: str) -> Dict[str, Any]:
    import json

    res = json.loads(Path(path).read_text(encoding="utf-8"))
    return cast(Dict[str, Any], res if isinstance(res, dict) else {})
