"""Append-only fsync-durable hash-chained JSONL audit log sink."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sentinel.domain.models import Incident


def compute_canonical_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of canonical JSON excluding 'hash' field."""
    payload = {k: v for k, v in data.items() if k != "hash"}
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class JSONLAuditLog:
    """Thread-safe, append-only, fsync-safe, hash-chained JSONL log sink with size-based rotation."""

    GENESIS_PREV_HASH = "0" * 64

    def __init__(
        self,
        log_path: Union[str, Path] = "logs/incidents.jsonl",
        max_bytes: int = 50 * 1024 * 1024,  # 50 MB
    ) -> None:
        self.path: Path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def _get_last_line_hash(self) -> str:
        """Retrieve the hash of the last entry in the log file, or GENESIS_PREV_HASH if empty."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return self.GENESIS_PREV_HASH

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                return self.GENESIS_PREV_HASH
            last_entry = json.loads(lines[-1])
            return str(last_entry.get("hash", self.GENESIS_PREV_HASH))
        except Exception:
            return self.GENESIS_PREV_HASH

    def record(self, incident: Incident) -> None:
        """Appends an incident to the log file with cryptographic hash chaining and fsync."""
        with self._lock:
            # Check rotation
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                self._rotate()

            prev_hash = self._get_last_line_hash()
            incident.prev_hash = prev_hash

            record_dict = incident.to_dict()
            record_dict["prev_hash"] = prev_hash
            record_dict.pop("hash", None)

            curr_hash = compute_canonical_hash(record_dict)
            record_dict["hash"] = curr_hash
            incident.hash = curr_hash

            payload = json.dumps(record_dict) + "\n"

            with open(self.path, "a", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        """Verifies the unbroken SHA-256 hash chain from genesis to tail.

        Returns (True, None) if completely intact, or (False, error_reason) if tampered.
        """
        if not self.path.exists():
            return True, None

        with self._lock:
            lines = [
                line.strip()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        if not lines:
            return True, None

        expected_prev = self.GENESIS_PREV_HASH

        for i, line in enumerate(lines):
            try:
                data: Dict[str, Any] = json.loads(line)
            except json.JSONDecodeError as exc:
                return False, f"Line {i}: JSON parse error: {exc}"

            line_prev = data.get("prev_hash")
            if line_prev != expected_prev:
                return (
                    False,
                    f"Line {i} chain broken: expected prev_hash '{expected_prev}', got '{line_prev}'",
                )

            recorded_hash = data.get("hash")
            if not recorded_hash:
                return False, f"Line {i} missing 'hash' signature"

            computed_hash = compute_canonical_hash(data)
            if recorded_hash != computed_hash:
                return (
                    False,
                    f"Line {i} content modified: recorded hash '{recorded_hash}' != computed hash '{computed_hash}'",
                )

            expected_prev = recorded_hash

        return True, None

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

    def update_clip_path(self, incident_id: str, clip_path: str) -> bool:
        """Updates the evidence clip path for an existing incident in the log."""
        if not self.path.exists():
            return False

        with self._lock:
            lines = [
                line.strip()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            updated = False
            entries = []
            for line in lines:
                try:
                    data = json.loads(line)
                    if data.get("incident_id") == incident_id:
                        data["evidence_clip"] = clip_path
                        data["evidence_status"] = "ready"
                        updated = True
                    entries.append(data)
                except Exception:
                    continue

            if updated:
                prev_h = self.GENESIS_PREV_HASH
                new_lines = []
                for entry in entries:
                    entry["prev_hash"] = prev_h
                    entry.pop("hash", None)
                    curr_h = compute_canonical_hash(entry)
                    entry["hash"] = curr_h
                    prev_h = curr_h
                    new_lines.append(json.dumps(entry))
                self.path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return updated


IncidentSink = JSONLAuditLog

__all__ = ["JSONLAuditLog", "IncidentSink", "compute_canonical_hash"]
