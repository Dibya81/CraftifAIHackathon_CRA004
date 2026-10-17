"""Rule engine for SiteSentinel: per-track deterministic state machines.

Rules implemented:
- NO_HELMET: Missing required helmet debounced for min_duration_s (default 2.0 s).
- NO_VEST: Missing required vest debounced for min_duration_s (default 2.0 s).
- ZONE_INTRUSION: Immediate incident raised on entry into a restricted or danger zone (once per entry).
- DANGER_DWELL: Raised when continuous dwell in a danger zone reaches dwell_s (default 5.0 s).

Invariants:
- Uses frame timestamps (ts) exclusively -- completely deterministic under replays.
- Purges lost tracks missing for > 2.0 s.
- One incident per continuous violation; re-alerts only after cooldown_s.
- Confidence = mean detection confidence accumulated across the violating window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sentinel.config import RulesConfig
from sentinel.models import FrameMeta, Incident
from sentinel.tracker_assoc import PersonPPEStatus, associate_ppe
from sentinel.zones import Zone, ZoneManager


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


class RuleEngine:
    """Processes per-frame detections and raises deterministic safety incidents."""

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
        self.tracks: Dict[int, TrackState] = {}
        self.last_frame_ts: Optional[float] = None

    def reset(self) -> None:
        """Clear all active track states (e.g. before replaying a clip)."""
        self.tracks.clear()
        self.last_frame_ts = None

    def _purge_lost_tracks(self, current_ts: float) -> None:
        """Purge tracks that have not been seen for more than LOST_TRACK_TIMEOUT_S."""
        lost = [
            t_id
            for t_id, state in self.tracks.items()
            if (current_ts - state.last_seen_ts) > self.LOST_TRACK_TIMEOUT_S
        ]
        for t_id in lost:
            del self.tracks[t_id]

    def process_frame(self, frame: FrameMeta) -> List[Incident]:
        """Process a single frame and return any newly generated incidents."""
        ts = frame.ts
        self.last_frame_ts = ts
        self._purge_lost_tracks(ts)

        incidents: List[Incident] = []

        # 1. Partition detections into person vs PPE
        persons = [
            d for d in frame.detections if d.class_name == "person" and d.track_id is not None
        ]
        ppe_dets = [
            d for d in frame.detections if d.class_name in {"helmet", "no_helmet", "head", "vest"}
        ]

        # 2. Frame dimensions for zone scaling
        fw = frame.frame.width if frame.frame else None
        fh = frame.frame.height if frame.frame else None

        # 3. Associate PPE with each person
        associations: List[PersonPPEStatus] = associate_ppe(
            persons, ppe_dets, self.rules_cfg.association
        )

        for status in associations:
            track_id = status.track_id
            if track_id is None:
                continue

            # Retrieve or create track state
            if track_id not in self.tracks:
                self.tracks[track_id] = TrackState(track_id=track_id, last_seen_ts=ts)
            track_state = self.tracks[track_id]
            track_state.last_seen_ts = ts

            # 4. Determine current spatial zone
            zone: Optional[Zone] = self.zone_mgr.find_best_zone_for_person(status.box, fw, fh)
            zone_id = zone.id if zone else None
            required_ppe = zone.required_ppe if zone else self.default_required_ppe

            # Evaluate rules for this person
            self._eval_no_helmet(status, track_state, zone_id, required_ppe, frame, incidents)
            self._eval_no_vest(status, track_state, zone_id, required_ppe, frame, incidents)
            self._eval_zone_intrusion(status, track_state, zone, frame, incidents)
            self._eval_danger_dwell(status, track_state, zone, frame, incidents)

            track_state.current_zone_id = zone_id

        return incidents

    def _eval_no_helmet(
        self,
        status: PersonPPEStatus,
        track_state: TrackState,
        zone_id: Optional[str],
        required_ppe: Set[str],
        frame: FrameMeta,
        out_incidents: List[Incident],
    ) -> None:
        cfg = self.rules_cfg.no_helmet
        if not cfg.enabled or "helmet" not in required_ppe:
            track_state.no_helmet.reset_violation()
            return

        is_missing = not status.has_helmet
        st = track_state.no_helmet

        if is_missing:
            # Use higher confidence if explicit no_helmet detection exists
            effective_conf = (
                max(status.person_conf, status.no_helmet_detection.conf)
                if status.explicit_no_helmet and status.no_helmet_detection
                else status.person_conf
            )
            st.record_violation(frame.ts, effective_conf)

            # Check debounce and cooldown
            assert st.violation_start_ts is not None
            duration = frame.ts - st.violation_start_ts
            can_raise = not st.incident_raised
            if st.incident_raised and st.last_raised_ts is not None:
                # Re-alert if duration exceeds cooldown_s since last raise
                if (frame.ts - st.last_raised_ts) >= self.rules_cfg.cooldown_s:
                    can_raise = True

            if duration >= cfg.min_duration_s and can_raise:
                inc = Incident.create(
                    incident_type="NO_HELMET",
                    severity=cfg.severity,
                    track_id=track_state.track_id,
                    camera_id=frame.camera_id,
                    confidence=st.mean_confidence,
                    duration_s=duration,
                    zone=zone_id,
                )
                st.incident_raised = True
                st.last_raised_ts = frame.ts
                out_incidents.append(inc)
        else:
            # Compliant now: reset violation state
            st.reset_violation()

    def _eval_no_vest(
        self,
        status: PersonPPEStatus,
        track_state: TrackState,
        zone_id: Optional[str],
        required_ppe: Set[str],
        frame: FrameMeta,
        out_incidents: List[Incident],
    ) -> None:
        cfg = self.rules_cfg.no_vest
        if not cfg.enabled or "vest" not in required_ppe:
            track_state.no_vest.reset_violation()
            return

        is_missing = not status.has_vest
        st = track_state.no_vest

        if is_missing:
            st.record_violation(frame.ts, status.person_conf)
            assert st.violation_start_ts is not None
            duration = frame.ts - st.violation_start_ts
            can_raise = not st.incident_raised
            if st.incident_raised and st.last_raised_ts is not None:
                if (frame.ts - st.last_raised_ts) >= self.rules_cfg.cooldown_s:
                    can_raise = True

            if duration >= cfg.min_duration_s and can_raise:
                inc = Incident.create(
                    incident_type="NO_VEST",
                    severity=cfg.severity,
                    track_id=track_state.track_id,
                    camera_id=frame.camera_id,
                    confidence=st.mean_confidence,
                    duration_s=duration,
                    zone=zone_id,
                )
                st.incident_raised = True
                st.last_raised_ts = frame.ts
                out_incidents.append(inc)
        else:
            st.reset_violation()

    def _eval_zone_intrusion(
        self,
        status: PersonPPEStatus,
        track_state: TrackState,
        zone: Optional[Zone],
        frame: FrameMeta,
        out_incidents: List[Incident],
    ) -> None:
        cfg = self.rules_cfg.zone_intrusion
        if not cfg.enabled:
            return

        is_restricted = zone is not None and zone.type in {"restricted", "danger"}
        st = track_state.zone_intrusion

        if is_restricted and zone is not None:
            # Check if this is a newly entered zone
            is_new_entry = track_state.current_zone_id != zone.id
            if is_new_entry:
                track_state.restricted_entry_ts = frame.ts
                st.is_violating = True
                st.violation_start_ts = frame.ts
                st.accumulated_confs = [status.person_conf]
                # If entering a new restricted zone or cooled down, raise immediately
                cooldown_ok = (
                    st.last_raised_ts is None
                    or (frame.ts - st.last_raised_ts) >= self.rules_cfg.cooldown_s
                )
                if cooldown_ok or not st.incident_raised:
                    inc = Incident.create(
                        incident_type="ZONE_INTRUSION",
                        severity=cfg.severity,
                        track_id=track_state.track_id,
                        camera_id=frame.camera_id,
                        confidence=status.person_conf,
                        duration_s=0.0,
                        zone=zone.id,
                    )
                    st.incident_raised = True
                    st.last_raised_ts = frame.ts
                    out_incidents.append(inc)
            else:
                st.accumulated_confs.append(status.person_conf)
        else:
            # Person has left restricted zone
            st.reset_violation()
            track_state.restricted_entry_ts = None

    def _eval_danger_dwell(
        self,
        status: PersonPPEStatus,
        track_state: TrackState,
        zone: Optional[Zone],
        frame: FrameMeta,
        out_incidents: List[Incident],
    ) -> None:
        cfg = self.rules_cfg.danger_dwell
        if not cfg.enabled:
            return

        is_in_danger = zone is not None and zone.type == "danger"
        st = track_state.danger_dwell

        if is_in_danger and zone is not None:
            if track_state.danger_entry_ts is None:
                track_state.danger_entry_ts = frame.ts
                st.record_violation(frame.ts, status.person_conf)
            else:
                st.record_violation(frame.ts, status.person_conf)

            dwell_time = frame.ts - track_state.danger_entry_ts
            can_raise = not st.incident_raised
            if st.incident_raised and st.last_raised_ts is not None:
                if (frame.ts - st.last_raised_ts) >= self.rules_cfg.cooldown_s:
                    can_raise = True

            if dwell_time >= cfg.dwell_s and can_raise:
                inc = Incident.create(
                    incident_type="DANGER_DWELL",
                    severity=cfg.severity,
                    track_id=track_state.track_id,
                    camera_id=frame.camera_id,
                    confidence=st.mean_confidence,
                    duration_s=dwell_time,
                    zone=zone.id,
                )
                st.incident_raised = True
                st.last_raised_ts = frame.ts
                out_incidents.append(inc)
        else:
            track_state.danger_entry_ts = None
            st.reset_violation()
