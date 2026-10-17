"""SQLite persistence adapter implementing IncidentRepository with WAL mode and outbox."""

from __future__ import annotations

import base64
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.domain.models import Incident, IncidentEvent


class SQLiteIncidentRepository:
    """Thread-safe SQLite repository supporting WAL, foreign keys, migrations, and transactional outbox."""

    def __init__(
        self,
        db_path: Union[str, Path] = "logs/sentinel.db",
        jsonl_log: Optional[JSONLAuditLog] = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_log = jsonl_log
        self._lock = threading.Lock()
        self._apply_migrations()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _apply_migrations(self) -> None:
        migrations_dir = Path(__file__).parent / "migrations"
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            # Find all .sql migrations sorted
            sql_files = sorted(migrations_dir.glob("*.sql"))
            for sql_file in sql_files:
                try:
                    version = int(sql_file.name.split("_")[0])
                except ValueError:
                    continue

                cursor = conn.execute(
                    "SELECT version FROM schema_migrations WHERE version = ?", (version,)
                )
                if cursor.fetchone() is None:
                    script = sql_file.read_text(encoding="utf-8")
                    conn.executescript(script)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, datetime.now(timezone.utc).isoformat()),
                    )
            conn.commit()

    def save_incident(
        self,
        incident: Incident,
        outbox_event: Optional[IncidentEvent] = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO incidents (
                    incident_id, timestamp, camera_id, type, severity, track_id,
                    zone, confidence, duration_s, evidence_clip, schema_version,
                    status, acked_at, acked_by, evidence_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.incident_id,
                    incident.timestamp,
                    incident.camera_id,
                    incident.type,
                    incident.severity,
                    incident.track_id,
                    incident.zone,
                    incident.confidence,
                    incident.duration_s,
                    incident.evidence_clip,
                    incident.schema_version,
                    incident.status,
                    incident.acked_at,
                    incident.acked_by,
                    incident.evidence_status,
                    now_iso,
                ),
            )

            # Insert outbox event in the same transaction
            if outbox_event is not None:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO outbox (
                        event_id, event_type, incident_id, payload, status, retry_count, created_at
                    ) VALUES (?, ?, ?, ?, 'pending', 0, ?)
                    """,
                    (
                        outbox_event.event_id,
                        outbox_event.event_type,
                        outbox_event.incident_id,
                        json.dumps(outbox_event.payload),
                        outbox_event.timestamp,
                    ),
                )
            conn.commit()

        # Synchronize with JSONL audit log
        if self.jsonl_log is not None:
            self.jsonl_log.record(incident)

    record_incident = save_incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
            if not row:
                return None

            notes_rows = conn.execute(
                "SELECT * FROM incident_notes WHERE incident_id = ? ORDER BY timestamp ASC",
                (incident_id,),
            ).fetchall()
            notes = [
                {
                    "note_id": nr["note_id"],
                    "timestamp": nr["timestamp"],
                    "author": nr["author"],
                    "note_text": nr["note_text"],
                }
                for nr in notes_rows
            ]

            return Incident(
                incident_id=row["incident_id"],
                timestamp=row["timestamp"],
                camera_id=row["camera_id"],
                type=row["type"],
                severity=row["severity"],
                track_id=row["track_id"],
                zone=row["zone"],
                confidence=float(row["confidence"]),
                duration_s=float(row["duration_s"]),
                evidence_clip=row["evidence_clip"],
                schema_version=row["schema_version"],
                status=row["status"],
                acked_at=row["acked_at"],
                acked_by=row["acked_by"],
                notes=notes,
                evidence_status=row["evidence_status"],
            )

    def list_incidents(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        since_iso: Optional[str] = None,
        until_iso: Optional[str] = None,
        incident_type: Optional[str] = None,
        zone: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[Incident], Optional[str]]:
        conditions: List[str] = []
        params: List[Any] = []

        if since_iso:
            conditions.append("timestamp >= ?")
            params.append(since_iso)
        if until_iso:
            conditions.append("timestamp <= ?")
            params.append(until_iso)
        if incident_type:
            conditions.append("type = ?")
            params.append(incident_type)
        if zone:
            conditions.append("zone = ?")
            params.append(zone)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search_query:
            conditions.append("(incident_id LIKE ? OR type LIKE ? OR zone LIKE ?)")
            q = f"%{search_query}%"
            params.extend([q, q, q])

        # Keyset pagination cursor
        if cursor:
            try:
                decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
                c_ts, c_id = decoded.split("::", 1)
                conditions.append("(timestamp < ? OR (timestamp = ? AND incident_id < ?))")
                params.extend([c_ts, c_ts, c_id])
            except Exception:
                pass

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM incidents
            {where_clause}
            ORDER BY timestamp DESC, incident_id DESC
            LIMIT ?
        """
        params.append(limit + 1)

        with self._lock, self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

            has_more = len(rows) > limit
            fetch_rows = rows[:limit]

            results: List[Incident] = []
            for r in fetch_rows:
                inc_id = r["incident_id"]
                n_rows = conn.execute(
                    "SELECT * FROM incident_notes WHERE incident_id = ? ORDER BY timestamp ASC",
                    (inc_id,),
                ).fetchall()
                notes = [
                    {
                        "note_id": nr["note_id"],
                        "timestamp": nr["timestamp"],
                        "author": nr["author"],
                        "note_text": nr["note_text"],
                    }
                    for nr in n_rows
                ]

                results.append(
                    Incident(
                        incident_id=r["incident_id"],
                        timestamp=r["timestamp"],
                        camera_id=r["camera_id"],
                        type=r["type"],
                        severity=r["severity"],
                        track_id=r["track_id"],
                        zone=r["zone"],
                        confidence=float(r["confidence"]),
                        duration_s=float(r["duration_s"]),
                        evidence_clip=r["evidence_clip"],
                        schema_version=r["schema_version"],
                        status=r["status"],
                        acked_at=r["acked_at"],
                        acked_by=r["acked_by"],
                        notes=notes,
                        evidence_status=r["evidence_status"],
                    )
                )

            next_cursor = None
            if has_more and fetch_rows:
                last_r = fetch_rows[-1]
                raw_cursor = f"{last_r['timestamp']}::{last_r['incident_id']}"
                next_cursor = base64.b64encode(raw_cursor.encode("utf-8")).decode("utf-8")

            return results, next_cursor

    def ack_incident(
        self,
        incident_id: str,
        acked_by: str = "safety-officer",
        note: Optional[str] = None,
        acked_at: Optional[str] = None,
    ) -> Optional[Incident]:
        ts = acked_at or datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE incidents
                SET status = 'acknowledged', acked_at = ?, acked_by = ?
                WHERE incident_id = ?
                """,
                (ts, acked_by, incident_id),
            )
            if cursor.rowcount == 0:
                return None

            if note:
                note_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO incident_notes (note_id, incident_id, timestamp, author, note_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (note_id, incident_id, ts, acked_by, note),
                )

            # Insert outbox event for ack
            conn.execute(
                """
                INSERT INTO outbox (event_id, event_type, incident_id, payload, status, retry_count, created_at)
                VALUES (?, 'incident_acked', ?, ?, 'pending', 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    incident_id,
                    json.dumps(
                        {
                            "incident_id": incident_id,
                            "acked_by": acked_by,
                            "acked_at": ts,
                            "note": note,
                        }
                    ),
                    ts,
                ),
            )
            conn.commit()

        return self.get_incident(incident_id)

    def add_note(
        self,
        incident_id: str,
        note_text: str,
        author: str = "safety-officer",
        timestamp: Optional[str] = None,
    ) -> Optional[Incident]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        note_id = str(uuid.uuid4())
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT incident_id FROM incidents WHERE incident_id = ?", (incident_id,)
            )
            if cursor.fetchone() is None:
                return None

            conn.execute(
                """
                INSERT INTO incident_notes (note_id, incident_id, timestamp, author, note_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (note_id, incident_id, ts, author, note_text),
            )

            conn.execute(
                """
                INSERT INTO outbox (event_id, event_type, incident_id, payload, status, retry_count, created_at)
                VALUES (?, 'incident_note_added', ?, ?, 'pending', 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    incident_id,
                    json.dumps(
                        {
                            "incident_id": incident_id,
                            "author": author,
                            "timestamp": ts,
                            "note": note_text,
                        }
                    ),
                    ts,
                ),
            )
            conn.commit()

        return self.get_incident(incident_id)

    def update_evidence(
        self,
        incident_id: str,
        clip_path: str,
        evidence_status: str = "ready",
    ) -> Optional[Incident]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE incidents
                SET evidence_clip = ?, evidence_status = ?
                WHERE incident_id = ?
                """,
                (clip_path, evidence_status, incident_id),
            )
            if cursor.rowcount == 0:
                return None

            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, incident_id, clip_path, thumbnail_path, duration_s, is_blurred, status, created_at
                ) VALUES (?, ?, ?, ?, 10.0, 1, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    incident_id,
                    clip_path,
                    clip_path.replace(".mp4", ".jpg"),
                    evidence_status,
                    now_iso,
                ),
            )

            conn.execute(
                """
                INSERT INTO outbox (event_id, event_type, incident_id, payload, status, retry_count, created_at)
                VALUES (?, 'incident_updated', ?, ?, 'pending', 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    incident_id,
                    json.dumps(
                        {
                            "incident_id": incident_id,
                            "evidence_clip": clip_path,
                            "evidence_status": evidence_status,
                        }
                    ),
                    now_iso,
                ),
            )
            conn.commit()

        return self.get_incident(incident_id)

    def get_pending_outbox_events(self, limit: int = 50) -> List[IncidentEvent]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, event_type, incident_id, payload, created_at
                FROM outbox
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            events: List[IncidentEvent] = []
            for r in rows:
                events.append(
                    IncidentEvent(
                        event_id=r["event_id"],
                        event_type=r["event_type"],
                        incident_id=r["incident_id"],
                        timestamp=r["created_at"],
                        payload=json.loads(r["payload"]),
                    )
                )
            return events

    def mark_outbox_event_published(self, event_id: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE outbox SET status = 'published', published_at = ? WHERE event_id = ?",
                (now_iso, event_id),
            )
            conn.commit()

    def get_stats(self, window_hours: int = 24) -> Dict[str, Any]:
        with self._lock, self._get_connection() as conn:
            total_row = conn.execute("SELECT COUNT(*) as cnt FROM incidents").fetchone()
            total_incidents = total_row["cnt"] if total_row else 0

            type_rows = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM incidents GROUP BY type"
            ).fetchall()
            by_type = {r["type"]: r["cnt"] for r in type_rows}

            zone_rows = conn.execute(
                "SELECT COALESCE(zone, 'unassigned') as z, COUNT(*) as cnt FROM incidents GROUP BY z"
            ).fetchall()
            by_zone = {r["z"]: r["cnt"] for r in zone_rows}

            sev_rows = conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM incidents GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            # Compliance % estimate: 100 - (incidents / 2.0 capped at 99%)
            compliance_pct = max(75.0, min(100.0, 100.0 - total_incidents * 1.5))

            return {
                "total_incidents": total_incidents,
                "compliance_pct": round(compliance_pct, 1),
                "by_type": by_type,
                "by_zone": by_zone,
                "by_severity": by_severity,
                "window_hours": window_hours,
            }
