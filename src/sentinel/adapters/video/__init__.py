"""Video adapter package for frame buffering, clip rendering, and MJPEG relay."""

from sentinel.adapters.video.clip_writer import EvidenceWriter, PrivacyViolationError
from sentinel.adapters.video.mjpeg_relay import MJPEGRelay
from sentinel.adapters.video.ring_buffer import RingBuffer

__all__ = [
    "EvidenceWriter",
    "MJPEGRelay",
    "PrivacyViolationError",
    "RingBuffer",
]
