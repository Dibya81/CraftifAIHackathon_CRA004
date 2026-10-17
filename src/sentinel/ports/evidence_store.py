"""EvidenceStore port for asynchronous clip writing and artifact queries."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, Tuple

from sentinel.domain.models import Incident


class EvidenceStore(Protocol):
    """Protocol for recording and retrieving face-blurred evidence clips and thumbnails."""

    def save_clip_async(
        self,
        incident: Incident,
        frames: List[Tuple[float, Any]],
        fps: float,
    ) -> None:
        """Asynchronously writes a 10s video clip and JPEG thumbnail."""
        ...

    def get_clip_path(self, incident_id: str) -> Optional[str]:
        """Resolves the relative or absolute path of an evidence clip."""
        ...

    def is_source_blurred(self) -> bool:
        """Verifies that the video source is certified face-blurred."""
        ...
