"""Append-only fsync-durable JSONL audit log sink."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sentinel.domain.models import Incident


class JSONLAuditLog:
    """Thread-safe, append-only, fsync-safe JSONL log sink with optional size-based rotation."""

    def __init__(
        self,
        log_path: Union[str, Path] = "logs/incidents.jsonl",
        max_bytes: int = 50 * 1024 * 1024,  # 50 MB
    ) -> None:
        self.path: Path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def record(self, incident: Incident) -> None:
        """Appends an incident to the log file and forces an fsync to persistent storage."""
        payload = json.dumps(incident.to_dict()) + "\n"
        with self._lock:
            # Check rotation
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                self._rotate()

            with open(self.path, "a", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

    def _rotate(self) -> None:
        """Rotates log file to .1, .2, etc."""
        backup_path = self.path.with_suffix(".jsonl.1")
        if backup_path.exists():
            backup_path.unlink()
        self.path.rename(backup_path)

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
                inc = Incident.from_dict(data)

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
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return results

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Finds an incident by its ID from the JSONL log file."""
        if not self.path.exists():
            return None

        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("incident_id") == incident_id:
                    return Incident.from_dict(data)
            except Exception:
                continue
        return None
