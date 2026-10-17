"""Asynchronous privacy-enforced evidence clip and thumbnail writer."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from sentinel.adapters.video.ring_buffer import RingBuffer
from sentinel.config import SentinelConfig
from sentinel.domain.models import Incident

logger = logging.getLogger("sentinel.adapters.video.clip_writer")


class PrivacyViolationError(RuntimeError):
    """Raised when an attempt is made to record or persist evidence from an unblurred video source."""

    pass


class EvidenceWriter:
    """Asynchronous, privacy-enforced evidence clip and thumbnail writer."""

    def __init__(
        self,
        config: SentinelConfig,
        is_source_blurred: bool = True,
        on_clip_saved_callback: Optional[Callable[[Incident, str], None]] = None,
        max_workers: int = 2,
    ) -> None:
        self.config = config
        self.evidence_dir = Path(config.paths.evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.is_source_blurred = is_source_blurred
        self.on_clip_saved_callback = on_clip_saved_callback

        # HARD RULE: Refuse to start if require_blurred_source is True and source is unblurred
        if config.privacy.require_blurred_source and not self.is_source_blurred:
            raise PrivacyViolationError(
                "HARD PRIVACY VIOLATION: Refusing to initialize EvidenceWriter because "
                "privacy.require_blurred_source is enabled and the video stream is not marked as blurred!"
            )

        self.pre_seconds = float(config.evidence.pre_seconds)
        self.post_seconds = float(config.evidence.post_seconds)

        max_buf_frames = int((self.pre_seconds + 5) * 30)
        self.ring_buffer = RingBuffer(max_frames=max(250, max_buf_frames))

        self._pending_jobs: List[Dict[str, Any]] = []
        self._jobs_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="evidence-writer"
        )

    def push_frame(self, ts: float, frame: np.ndarray) -> None:
        """Pushes a newly arrived frame to the buffer and updates active clip recording jobs."""
        if self.config.privacy.require_blurred_source and not self.is_source_blurred:
            raise PrivacyViolationError("Cannot push frame: video source is not marked blurred.")

        self.ring_buffer.append(ts, frame)

        # Check pending clip capture jobs
        jobs_to_finalize: List[Dict[str, Any]] = []
        with self._jobs_lock:
            for job in list(self._pending_jobs):
                job["post_frames"].append((ts, frame.copy()))
                if (ts - job["trigger_ts"]) >= self.post_seconds:
                    jobs_to_finalize.append(job)
                    self._pending_jobs.remove(job)

        for job in jobs_to_finalize:
            self._executor.submit(self._finalize_clip, job)

    def trigger_incident(self, incident: Incident, trigger_ts: Optional[float] = None) -> None:
        """Initiates evidence clip collection for the given incident."""
        if trigger_ts is None:
            trigger_ts = time.time()

        # Capture pre-incident frames from buffer
        start_ts = trigger_ts - self.pre_seconds
        pre_frames = [
            (t, f.copy()) for t, f in self.ring_buffer.snapshot() if start_ts <= t <= trigger_ts
        ]

        job = {
            "incident": incident,
            "trigger_ts": trigger_ts,
            "pre_frames": pre_frames,
            "post_frames": [],
            "start_time": time.time(),
        }

        with self._jobs_lock:
            self._pending_jobs.append(job)

    def finalize_dropped_stream(self) -> None:
        """If a stream drops or disconnects, finalize any in-flight jobs as partial clips."""
        with self._jobs_lock:
            jobs = list(self._pending_jobs)
            self._pending_jobs.clear()

        for job in jobs:
            job["incident"].evidence_status = "partial"
            self._executor.submit(self._finalize_clip, job)

    def _finalize_clip(self, job: Dict[str, Any]) -> Optional[str]:
        incident: Incident = job["incident"]
        all_frames: List[Tuple[float, np.ndarray]] = job["pre_frames"] + job["post_frames"]

        if not all_frames:
            logger.warning("No frames captured for incident %s", incident.incident_id)
            return None

        # Build output directory: evidence/YYYY-MM-DD/
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = self.evidence_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        clip_filename = f"{incident.incident_id}.mp4"
        thumb_filename = f"{incident.incident_id}.jpg"
        clip_path = day_dir / clip_filename
        thumb_path = day_dir / thumb_filename
        temp_clip_path = day_dir / f"{incident.incident_id}.tmp.mp4"

        h, w = all_frames[0][1].shape[:2]
        fps = 25.0
        if len(all_frames) >= 2:
            duration = all_frames[-1][0] - all_frames[0][0]
            if duration > 0:
                fps = max(5.0, min(60.0, len(all_frames) / duration))

        # Defense-in-depth privacy check across sampled frames
        sample_indices = np.linspace(0, len(all_frames) - 1, min(10, len(all_frames)), dtype=int)
        for idx in sample_indices:
            frame_sample = all_frames[idx][1]
            if self.audit_frame_for_unblurred_faces(frame_sample):
                logger.warning(
                    "PRIVACY_WARNING: Potential unblurred face detected in frame %d for incident %s!",
                    idx,
                    incident.incident_id,
                )

        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
            writer = cv2.VideoWriter(str(temp_clip_path), fourcc, fps, (w, h))
            for _, frame in all_frames:
                writer.write(frame)
            writer.release()

            # Save JPEG thumbnail at middle frame
            mid_idx = len(all_frames) // 2
            cv2.imwrite(str(thumb_path), all_frames[mid_idx][1])

            # Atomic rename
            temp_clip_path.replace(clip_path)

            rel_clip_path = str(clip_path.relative_to(self.evidence_dir.parent))
            incident.evidence_clip = rel_clip_path
            if incident.evidence_status != "partial":
                incident.evidence_status = "ready"

            logger.info("Saved evidence clip: %s (%d frames)", clip_path, len(all_frames))

            if self.on_clip_saved_callback is not None:
                self.on_clip_saved_callback(incident, rel_clip_path)

            return rel_clip_path

        except Exception as exc:
            logger.error("Failed to write evidence clip for %s: %s", incident.incident_id, exc)
            if temp_clip_path.exists():
                try:
                    temp_clip_path.unlink()
                except Exception:
                    pass
            incident.evidence_status = "failed"
            return None

    def audit_frame_for_unblurred_faces(self, frame: np.ndarray) -> bool:
        """Returns True if a legible unblurred face is detected (secondary defense check)."""
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
            cv2_data = getattr(cv2, "data", None)
            cascade_path = (
                getattr(cv2_data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
            )
            if Path(cascade_path).is_file():
                try:
                    cascade = cv2.CascadeClassifier(cascade_path)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                    )
                    if len(faces) > 0:
                        return True
                except Exception:
                    pass

        try:
            ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
            contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w >= 30 and h >= 30 and 0.7 <= (h / w) <= 1.6:
                    roi = frame[y : y + h, x : x + w]
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                    if lap_var > 150.0:
                        return True
        except Exception:
            pass
        return False

    def shutdown(self, wait: bool = True) -> None:
        """Shuts down worker threads, waiting for pending clips to render if wait=True."""
        self._executor.shutdown(wait=wait)

    def close(self) -> None:
        self.shutdown(wait=False)
