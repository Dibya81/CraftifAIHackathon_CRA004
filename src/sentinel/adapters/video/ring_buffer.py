"""Thread-safe rolling frame ring buffer with presentation timestamps."""

from __future__ import annotations

import collections
import threading
from typing import Any, Deque, List, Tuple


class RingBuffer:
    """Thread-safe rolling buffer of video frames with presentation timestamps."""

    def __init__(self, max_frames: int = 250) -> None:
        self.max_frames = max_frames
        self._buffer: Deque[Tuple[float, Any]] = collections.deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def append(self, ts: float, frame: Any) -> None:
        with self._lock:
            # Store copy or immutable view to avoid external mutations
            frame_data = frame.copy() if hasattr(frame, "copy") else frame
            self._buffer.append((ts, frame_data))

    def snapshot(self) -> List[Tuple[float, Any]]:
        with self._lock:
            return list(self._buffer)

    def get_frames_in_range(self, start_ts: float, end_ts: float) -> List[Tuple[float, Any]]:
        with self._lock:
            return [(ts, f) for ts, f in self._buffer if start_ts <= ts <= end_ts]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
