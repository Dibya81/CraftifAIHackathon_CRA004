"""Rolling frame ring buffer and privacy-enforced evidence clip writer.

Re-exports core evidence components from sentinel.adapters.video for backward compatibility.
"""

from __future__ import annotations

from sentinel.adapters.video.clip_writer import EvidenceWriter, PrivacyViolationError
from sentinel.adapters.video.ring_buffer import RingBuffer

__all__ = [
    "EvidenceWriter",
    "PrivacyViolationError",
    "RingBuffer",
]
