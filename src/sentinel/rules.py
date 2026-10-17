"""Backward-compatible rule engine module re-exporting domain rules."""

from __future__ import annotations

from sentinel.domain.rules import (
    EngineState,
    RuleEngine,
    RuleState,
    TrackState,
    purge_lost_tracks,
    step,
)

__all__ = [
    "EngineState",
    "RuleEngine",
    "RuleState",
    "TrackState",
    "purge_lost_tracks",
    "step",
]
