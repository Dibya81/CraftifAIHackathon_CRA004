"""Incident model, JSONL append-only log sink (fsync-safe), and query helpers.

Ensures every generated incident is durably committed to disk with fsync before returning.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sentinel.models import Incident


class IncidentSink:
    """Thread-safe, append-only, fsync-safe JSONL log sink for safety incidents."""

    def __init__(self, log_path: Union[str, Path] = "logs/incidents.jsonl") -> None:
        self.path: Path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, incident: Incident) -> None:
        """Appends an incident to the log file and forces an fsync to persistent storage."""
        payload = json.dumps(incident.to_dict()) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

    def read_all(
        self,
        limit: Optional[int] = None,
        since_iso: Optional[str] = None,
        incident_type: Optional[str] = None,
        zone: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Incident]:
        """Reads and filters incidents from the log file, ordered newest first."""
        if not self.path.exists():
            return []

        results: List[Incident] = []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data: Dict[str, Any] = json.loads(line)
                inc = Incident(
                    incident_id=data["incident_id"],
                    timestamp=data["timestamp"],
                    camera_id=data["camera_id"],
                    type=data["type"],
                    severity=data["severity"],
                    track_id=int(data["track_id"]),
                    zone=data.get("zone"),
                    confidence=float(data["confidence"]),
                    duration_s=float(data["duration_s"]),
                    evidence_clip=data.get("evidence_clip"),
                )
            except Exception:
                continue

            if since_iso and inc.timestamp < since_iso:
                continue
            if incident_type and inc.type != incident_type:
                continue
            if zone and inc.zone != zone:
                continue
            if severity and inc.severity != severity:
                continue

            results.append(inc)
            if limit and len(results) >= limit:
                break

        return results

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Look up a specific incident by ID."""
        for inc in self.read_all():
            if inc.incident_id == incident_id:
                return inc
        return None

    def update_clip_path(self, incident_id: str, clip_path: str) -> bool:
        """Update the evidence clip path for an incident in the log."""
        if not self.path.exists():
            return False

        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            updated = False
            new_lines = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("incident_id") == incident_id:
                        data["evidence_clip"] = clip_path
                        updated = True
                    new_lines.append(json.dumps(data))
                except Exception:
                    new_lines.append(line)

            if updated:
                tmp_path = self.path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    for nl in new_lines:
                        f.write(nl + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                tmp_path.replace(self.path)
            return updated
