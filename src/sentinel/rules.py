"""Rule engine: per-track state machines for NO_HELMET, NO_VEST, ZONE_INTRUSION, DANGER_DWELL.

Responsibilities: duration thresholds, debounce (one incident per continuous violation),
cooldown before re-alert, severity assignment.
"""
# TODO: class RuleEngine: process_frame(frame_meta) -> list[Incident]
