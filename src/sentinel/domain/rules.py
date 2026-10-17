"""Pure domain rule engine and per-track state machines.

Core pure function:
  step(state, frame, zone_manager, config) -> (new_state, incidents)

Invariants:
- Uses frame timestamps (ts) exclusively -- completely deterministic under replays.
- Purges lost tracks missing for > 2.0 s.
- At most one open incident per (track, type, zone) at a time.
- No incident raised before the duration threshold (min_duration_s).
- Cooldown suppression before re-alerting.
- Confidence is the mean detection confidence accumulated across the violating window.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from sentinel.config import RulesConfig
from sentinel.domain.association import associate_ppe
from sentinel.domain.models import FrameMeta, Incident
from sentinel.domain.zones import ZoneManager


@dataclass
class RuleState:
    """State machine tracker for a single violation type on a track."""

    is_violating: bool = False
    violation_start_ts: Optional[float] = None
    incident_raised: bool = False
    last_raised_ts: Optional[float] = None
    accumulated_confs: List[float] = field(default_factory=list)

    def record_violation(self, ts: float, conf: float) -> None:
        if not self.is_violating:
            self.is_violating = True
            self.violation_start_ts = ts
            self.accumulated_confs = [conf]
        else:
            self.accumulated_confs.append(conf)

    def reset_violation(self) -> None:
        self.is_violating = False
        self.violation_start_ts = None
        self.accumulated_confs.clear()
        self.incident_raised = False

    @property
    def mean_confidence(self) -> float:
        if not self.accumulated_confs:
            return 0.8
        return sum(self.accumulated_confs) / len(self.accumulated_confs)


@dataclass
class TrackState:
    """Complete multi-rule state for a single tracked person."""

    track_id: int
    last_seen_ts: float
    current_zone_id: Optional[str] = None
    danger_entry_ts: Optional[float] = None
    restricted_entry_ts: Optional[float] = None

    # Rule sub-states
    no_helmet: RuleState = field(default_factory=RuleState)
    no_vest: RuleState = field(default_factory=RuleState)
    zone_intrusion: RuleState = field(default_factory=RuleState)
    danger_dwell: RuleState = field(default_factory=RuleState)


@dataclass
class EngineState:
    """Immutable or copyable container holding all tracked persons and timestamps."""

    tracks: Dict[int, TrackState] = field(default_factory=dict)
    last_frame_ts: Optional[float] = None


def purge_lost_tracks(
    tracks: Dict[int, TrackState], current_ts: float, timeout_s: float = 2.0
) -> Dict[int, TrackState]:
    """Returns tracks pruned of targets not seen for > timeout_s."""
    active: Dict[int, TrackState] = {}
    for tid, st in tracks.items():
        if current_ts - st.last_seen_ts <= timeout_s:
            active[tid] = st
    return active


def step(
    state: EngineState,
    frame: FrameMeta,
    zone_manager: ZoneManager,
    rules_cfg: RulesConfig,
    default_required_ppe: Optional[Set[str]] = None,
) -> Tuple[EngineState, List[Incident]]:
    """Pure state machine step: evaluates frame and returns (new_state, raised_incidents)."""
    current_ts = frame.ts
    default_ppe = default_required_ppe if default_required_ppe is not None else {"helmet"}

    # Copy / clone state for pure evaluation
    new_tracks = purge_lost_tracks(copy.deepcopy(state.tracks), current_ts, timeout_s=2.0)
    incidents: List[Incident] = []

    # 1. Split detections
    person_dets = [
        d for d in frame.detections if d.class_name == "person" and d.track_id is not None
    ]
    ppe_dets = [
        d for d in frame.detections if d.class_name in {"helmet", "no_helmet", "head", "vest"}
    ]

    frame_w = frame.frame.width if frame.frame else None
    frame_h = frame.frame.height if frame.frame else None

    # 2. Anatomical association
    assoc_cfg = rules_cfg.association
    ppe_statuses = associate_ppe(
        persons=person_dets,
        ppe_detections=ppe_dets,
        head_region=assoc_cfg.head_region,
        torso_region=assoc_cfg.torso_region,
        min_overlap=assoc_cfg.min_overlap,
    )

    # 3. Process each tracked person
    for status in ppe_statuses:
        track_id = status.track_id
        if track_id is None:
            continue

        box = status.box
        zone = zone_manager.find_best_zone_for_person(box, frame_w, frame_h)
        zone_id = zone.id if zone else None
        required_ppe = zone.required_ppe if zone else default_ppe

        if track_id not in new_tracks:
            new_tracks[track_id] = TrackState(track_id=track_id, last_seen_ts=current_ts)
        t_state = new_tracks[track_id]
        t_state.last_seen_ts = current_ts

        # Zone transitions
        if t_state.current_zone_id != zone_id:
            t_state.current_zone_id = zone_id
            if zone and zone.type == "danger":
                t_state.danger_entry_ts = current_ts
                t_state.danger_dwell.reset_violation()
            else:
                t_state.danger_entry_ts = None
                t_state.danger_dwell.reset_violation()

            if zone and zone.type in {"restricted", "danger"}:
                t_state.restricted_entry_ts = current_ts
                t_state.zone_intrusion.reset_violation()
            else:
                t_state.restricted_entry_ts = None
                t_state.zone_intrusion.reset_violation()

        cooldown_s = getattr(rules_cfg, "cooldown_s", 30.0)

        # Rule A: NO_HELMET
        if "helmet" in required_ppe and not status.has_helmet:
            conf = (
                status.no_helmet_detection.conf
                if status.explicit_no_helmet and status.no_helmet_detection
                else status.person_conf
            )
            inc = _evaluate_debounced_rule(
                rule_state=t_state.no_helmet,
                current_ts=current_ts,
                conf=conf,
                incident_type="NO_HELMET",
                severity=rules_cfg.no_helmet.severity,
                min_duration_s=rules_cfg.no_helmet.min_duration_s,
                cooldown_s=cooldown_s,
                track_id=track_id,
                camera_id=frame.camera_id,
                zone_id=zone_id,
            )
            if inc:
                incidents.append(inc)
        else:
            t_state.no_helmet.reset_violation()

        # Rule B: NO_VEST
        if "vest" in required_ppe and not status.has_vest:
            inc = _evaluate_debounced_rule(
                rule_state=t_state.no_vest,
                current_ts=current_ts,
                conf=status.person_conf,
                incident_type="NO_VEST",
                severity=rules_cfg.no_vest.severity,
                min_duration_s=rules_cfg.no_vest.min_duration_s,
                cooldown_s=cooldown_s,
                track_id=track_id,
                camera_id=frame.camera_id,
                zone_id=zone_id,
            )
            if inc:
                incidents.append(inc)
        else:
            t_state.no_vest.reset_violation()

        # Rule C: ZONE_INTRUSION
        if zone and zone.type in {"restricted", "danger"}:
            inc = _evaluate_zone_intrusion(
                rule_state=t_state.zone_intrusion,
                current_ts=current_ts,
                conf=status.person_conf,
                severity=rules_cfg.zone_intrusion.severity,
                cooldown_s=cooldown_s,
                track_id=track_id,
                camera_id=frame.camera_id,
                zone_id=zone_id,
            )
            if inc:
                incidents.append(inc)
        else:
            t_state.zone_intrusion.reset_violation()

        # Rule D: DANGER_DWELL
        if zone and zone.type == "danger" and t_state.danger_entry_ts is not None:
            dwell_duration = current_ts - t_state.danger_entry_ts
            if dwell_duration >= rules_cfg.danger_dwell.dwell_s:
                inc = _evaluate_danger_dwell(
                    rule_state=t_state.danger_dwell,
                    current_ts=current_ts,
                    dwell_duration=dwell_duration,
                    conf=status.person_conf,
                    severity=rules_cfg.danger_dwell.severity,
                    cooldown_s=cooldown_s,
                    track_id=track_id,
                    camera_id=frame.camera_id,
                    zone_id=zone_id,
                )
                if inc:
                    incidents.append(inc)
        else:
            t_state.danger_dwell.reset_violation()

    new_state = EngineState(tracks=new_tracks, last_frame_ts=current_ts)
    return new_state, incidents


def _evaluate_debounced_rule(
    rule_state: RuleState,
    current_ts: float,
    conf: float,
    incident_type: str,
    severity: str,
    min_duration_s: float,
    cooldown_s: float,
    track_id: int,
    camera_id: str,
    zone_id: Optional[str],
) -> Optional[Incident]:
    rule_state.record_violation(current_ts, conf)

    if rule_state.last_raised_ts is not None:
        if current_ts - rule_state.last_raised_ts < cooldown_s:
            return None

    if rule_state.incident_raised:
        return None

    if rule_state.violation_start_ts is None:
        return None

    elapsed_s = current_ts - rule_state.violation_start_ts
    if elapsed_s >= min_duration_s:
        rule_state.incident_raised = True
        rule_state.last_raised_ts = current_ts
        return Incident.create(
            incident_type=incident_type,
            severity=severity,
            track_id=track_id,
            camera_id=camera_id,
            confidence=rule_state.mean_confidence,
            duration_s=elapsed_s,
            zone=zone_id,
        )
    return None


def _evaluate_zone_intrusion(
    rule_state: RuleState,
    current_ts: float,
    conf: float,
    severity: str,
    cooldown_s: float,
    track_id: int,
    camera_id: str,
    zone_id: Optional[str],
) -> Optional[Incident]:
    if rule_state.last_raised_ts is not None:
        if current_ts - rule_state.last_raised_ts < cooldown_s:
            return None

    if rule_state.incident_raised:
        return None

    rule_state.record_violation(current_ts, conf)
    rule_state.incident_raised = True
    rule_state.last_raised_ts = current_ts

    return Incident.create(
        incident_type="ZONE_INTRUSION",
        severity=severity,
        track_id=track_id,
        camera_id=camera_id,
        confidence=conf,
        duration_s=0.0,
        zone=zone_id,
    )


def _evaluate_danger_dwell(
    rule_state: RuleState,
    current_ts: float,
    dwell_duration: float,
    conf: float,
    severity: str,
    cooldown_s: float,
    track_id: int,
    camera_id: str,
    zone_id: Optional[str],
) -> Optional[Incident]:
    if rule_state.last_raised_ts is not None:
        if current_ts - rule_state.last_raised_ts < cooldown_s:
            return None

    rule_state.record_violation(current_ts, conf)
    rule_state.last_raised_ts = current_ts

    return Incident.create(
        incident_type="DANGER_DWELL",
        severity=severity,
        track_id=track_id,
        camera_id=camera_id,
        confidence=rule_state.mean_confidence,
        duration_s=dwell_duration,
        zone=zone_id,
    )


class RuleEngine:
    """Stateful wrapper managing EngineState across streaming frames."""

    LOST_TRACK_TIMEOUT_S: float = 2.0

    def __init__(
        self,
        rules_cfg: RulesConfig,
        zone_manager: ZoneManager,
        default_required_ppe: Optional[Set[str]] = None,
    ) -> None:
        self.rules_cfg: RulesConfig = rules_cfg
        self.zone_mgr: ZoneManager = zone_manager
        self.default_required_ppe: Set[str] = (
            default_required_ppe if default_required_ppe is not None else {"helmet"}
        )
        self._state: EngineState = EngineState()

    @property
    def tracks(self) -> Dict[int, TrackState]:
        return self._state.tracks

    @property
    def last_frame_ts(self) -> Optional[float]:
        return self._state.last_frame_ts

    def reset(self) -> None:
        self._state = EngineState()

    def process_frame(self, frame: FrameMeta) -> List[Incident]:
        self._state, incidents = step(
            state=self._state,
            frame=frame,
            zone_manager=self.zone_mgr,
            rules_cfg=self.rules_cfg,
            default_required_ppe=self.default_required_ppe,
        )
        return incidents
