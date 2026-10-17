"""MJPEG video stream relay and snapshot cache with clean fan-out to N clients."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import AsyncGenerator, Optional

import cv2
import numpy as np

logger = logging.getLogger("sentinel.adapters.video.mjpeg_relay")


class MJPEGRelay:
    """Single shared frame relay supporting fan-out to N HTTP clients with FPS cap and snapshot cache."""

    def __init__(self, jpeg_quality: int = 80, default_fps_cap: float = 15.0) -> None:
        self.jpeg_quality = jpeg_quality
        self.default_fps_cap = default_fps_cap
        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_timestamp: float = 0.0

    def update_frame(self, frame: np.ndarray, timestamp: Optional[float] = None) -> None:
        """Encodes frame to JPEG and caches it for snapshots and MJPEG streaming."""
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return

        ts = timestamp if timestamp is not None else time.time()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        success, buffer = cv2.imencode(".jpg", frame, encode_param)
        if success:
            jpeg_bytes = buffer.tobytes()
            with self._lock:
                self._latest_jpeg = jpeg_bytes
                self._latest_frame = frame.copy()
                self._latest_timestamp = ts

    def get_snapshot_jpeg(self) -> Optional[bytes]:
        """Returns the latest JPEG snapshot bytes."""
        with self._lock:
            return self._latest_jpeg

    def get_snapshot_frame(self) -> Optional[np.ndarray]:
        """Returns the latest raw numpy frame."""
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    async def stream_generator(
        self, fps_cap: Optional[float] = None
    ) -> AsyncGenerator[bytes, None]:
        """Async generator yielding multipart JPEG frames for HTTP MJPEG streaming."""
        cap = fps_cap if fps_cap is not None else self.default_fps_cap
        interval = 1.0 / max(1.0, cap)
        last_sent_ts = 0.0

        try:
            while True:
                with self._lock:
                    jpeg = self._latest_jpeg
                    ts = self._latest_timestamp

                if jpeg is not None and ts > last_sent_ts:
                    last_sent_ts = ts
                    chunk = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: "
                        + str(len(jpeg)).encode("ascii")
                        + b"\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                    yield chunk

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.debug("MJPEG client disconnected cleanly.")
            raise
