"""SystemProbe port for hardware telemetry and environment diagnostics."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class SystemProbe(Protocol):
    """Protocol for sampling CPU, memory, GPU, and PipeGen health telemetry."""

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns structured system telemetry dictionary."""
        ...
