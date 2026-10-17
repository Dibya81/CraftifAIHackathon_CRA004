"""Incident log sink and persistence helper."""

from __future__ import annotations

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog


class IncidentSink(JSONLAuditLog):
    """Backward-compatible IncidentSink wrapping JSONLAuditLog with clip update helper."""

    def update_clip_path(self, incident_id: str, clip_path: str) -> bool:
        """Updates the evidence clip path for an existing incident in the log."""
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
                        data["evidence_status"] = "ready"
                        updated = True
                        new_lines.append(json.dumps(data))
                    else:
                        new_lines.append(line)
                except Exception:
                    new_lines.append(line)

            if updated:
                self.path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return updated


import json  # noqa: E402

__all__ = ["IncidentSink"]
