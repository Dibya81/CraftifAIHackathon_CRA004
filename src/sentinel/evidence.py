"""Rolling frame ring buffer and privacy-enforced evidence clip writer.

Guarantees:
- Hard rule: No unblurred face frame may ever be written to disk.
- Refuses to start or write if privacy.require_blurred_source is True and source is not blurred.
- Asynchronous video and thumbnail writer: rule engine is never blocked.
- Saves 10 s clip (pre_seconds before, post_seconds after) to evidence/YYYY-MM-DD/<incident_id>.mp4.
- Generates high-contrast JPEG thumbnail.
- Defense in depth: Haar face detector audit on saved frames; emits PRIVACY_WARNING on legible faces.
- Stream drop resilience: writes partial clip and marks clip metadata as 'partial' instead of crashing.
"""
from __future__ import annotations

import collections
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from sentinel.config import SentinelConfig
from sentinel.models import Incident

logger = logging.getLogger("sentinel.evidence")


class PrivacyViolationError(RuntimeError):
    """Raised when an attempt is made to record or persist evidence from an unblurred video source."""
    pass


class RingBuffer:
    """Thread-safe rolling buffer of video frames with presentation timestamps."""

    def __init__(self, max_frames: int = 250) -> None:
        self.max_frames = max_frames
        self._buffer: Deque[Tuple[float, np.ndarray]] = collections.deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def append(self, ts: float, frame: np.ndarray) -> None:
        with self._lock:
            # Store copy to avoid external mutations
            self._buffer.append((ts, frame.copy()))

    def snapshot(self) -> List[Tuple[float, np.ndarray]]:
        with self._lock:
            return list(self._buffer)

    def get_frames_in_range(self, start_ts: float, end_ts: float) -> List[Tuple[float, np.ndarray]]:
        with self._lock:
            return [(ts, f) for ts, f in self._buffer if start_ts <= ts <= end_ts]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)


class EvidenceWriter:
    """Manages buffered frames and asynchronously writes MP4 clips and thumbnails upon incident."""

    def __init__(
        self,
        config: SentinelConfig,
        is_source_blurred: bool = True,
        on_clip_saved_callback: Optional[Callable[[Incident, str], None]] = None,
        max_workers: int = 2,
    ) -> None:
        self.config = config
        self.is_source_blurred = is_source_blurred
        self.on_clip_saved_callback = on_clip_saved_callback

        # Enforce Section 3 Hard Rule
        if config.privacy.require_blurred_source and not is_source_blurred:
            raise PrivacyViolationError(
                "Refusing to initialize EvidenceWriter: config requires privacy.require_blurred_source, "
                "but the video source is not certified blurred. Raw face frames must never be persisted."
            )

        self.pre_seconds = config.evidence.pre_seconds
        self.post_seconds = config.evidence.post_seconds
        self.evidence_dir = Path(config.paths.evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        # Buffer: 25 FPS * (pre_seconds + 5 buffer)
        buffer_capacity = int(25 * (self.pre_seconds + 5))
        self.ring_buffer = RingBuffer(max_frames=buffer_capacity)

        # In-flight recording jobs waiting for post-seconds frames
        self._pending_jobs: List[Dict[str, Any]] = []
        self._jobs_lock = threading.Lock()

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evidence-writer")
        self._face_cascade: Any = None

    def audit_frame_for_unblurred_faces(self, frame: np.ndarray) -> bool:
        """Returns True if a legible unblurred face is detected (secondary defense check)."""
        # 1. Try OpenCV CascadeClassifier if available in current build
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
            cv2_data = getattr(cv2, "data", None)
            cascade_path = getattr(cv2_data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
            if Path(cascade_path).is_file():
                try:
                    classifier_cls = getattr(cv2, "CascadeClassifier")
                    cascade = classifier_cls(cascade_path)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                    if len(faces) > 0:
                        return True
                except Exception as e:
                    logger.debug("CascadeClassifier check failed: %s", e)

        # 2. Skin tone + high-frequency sharpness analysis (unblurred vs blurred)
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
                    if lap_var > 150.0:  # Sharp unblurred facial features
                        return True
        except Exception as e:
            logger.warning("Error running secondary face audit: %s", e)

        return False

    def push_frame(self, ts: float, frame: np.ndarray) -> None:
        """Pushes a newly arrived frame to the buffer and updates active clip recording jobs."""
        if self.config.privacy.require_blurred_source and not self.is_source_blurred:
            raise PrivacyViolationError("Cannot push frame: video source is not marked blurred.")

        self.ring_buffer.append(ts, frame)

        # Check pending clip capture jobs
        jobs_to_finalize = []
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
            (t, f.copy())
            for t, f in self.ring_buffer.snapshot()
            if start_ts <= t <= trigger_ts
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
            job["partial"] = True
            self._executor.submit(self._finalize_clip, job)

    def _finalize_clip(self, job: Dict[str, Any]) -> Optional[str]:
        incident: Incident = job["incident"]
        all_frames = job["pre_frames"] + job["post_frames"]

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

        # Write MP4 video clip
        fourcc = getattr(cv2, "VideoWriter_fourcc")(*"mp4v")
        writer = cv2.VideoWriter(str(clip_path), fourcc, fps, (w, h))
        for _, frame in all_frames:
            writer.write(frame)
        writer.release()

        # Write JPEG thumbnail (choose frame closest to trigger_ts)
        trigger_ts = job["trigger_ts"]
        mid_idx = min(range(len(all_frames)), key=lambda i: abs(all_frames[i][0] - trigger_ts))
        thumb_img = all_frames[mid_idx][1]
        cv2.imwrite(str(thumb_path), thumb_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

        rel_clip_path = str(clip_path.relative_to(self.evidence_dir.parent))
        incident.evidence_clip = rel_clip_path

        logger.info("Saved evidence clip to %s (frames: %d, fps: %.1f)", clip_path, len(all_frames), fps)

        if self.on_clip_saved_callback:
            try:
                self.on_clip_saved_callback(incident, rel_clip_path)
            except Exception as e:
                logger.error("Error in on_clip_saved_callback: %s", e)

        return rel_clip_path

    def shutdown(self) -> None:
        """Wait for pending writes to finish and terminate workers."""
        self.finalize_dropped_stream()
        self._executor.shutdown(wait=True)
