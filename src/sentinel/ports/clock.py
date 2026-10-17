"""Clock port for deterministic domain execution and testing."""

from __future__ import annotations

import datetime
from typing import Protocol


class Clock(Protocol):
    """Protocol for time querying, enabling deterministic replays."""

    def now(self) -> float:
        """Returns epoch seconds as a float."""
        ...

    def now_iso(self) -> str:
        """Returns ISO-8601 UTC timestamp string."""
        ...


class SystemClock:
    """Standard system wall clock."""

    def now(self) -> float:
        return datetime.datetime.now(datetime.timezone.utc).timestamp()

    def now_iso(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


class InjectedClock:
    """Deterministic, controllable clock for unit tests and simulation."""

    def __init__(self, initial_ts: float = 1700000000.0) -> None:
        self._current_ts = float(initial_ts)

    def now(self) -> float:
        return self._current_ts

    def now_iso(self) -> str:
        dt = datetime.datetime.fromtimestamp(self._current_ts, tz=datetime.timezone.utc)
        return dt.isoformat()

    def advance(self, seconds: float) -> None:
        self._current_ts += float(seconds)

    def set(self, timestamp: float) -> None:
        self._current_ts = float(timestamp)
