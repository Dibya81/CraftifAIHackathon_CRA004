"""Rolling frame buffer and evidence clip writer (5 s before, 5 s after).

Frames must come from the PipeGen face-blurred branch so no unblurred face is persisted.
"""
# TODO: RingBuffer, EvidenceWriter.save(incident) -> clip path
