"""Tests for structured logging."""

import json
import logging
from pathlib import Path

from sentinel.logging import setup_logging


def test_structured_logging(tmp_path: Path):
    log_file = tmp_path / "test.log"
    logger = setup_logging(log_file=str(log_file), level=logging.INFO, console=False)
    logger.info("Test event occurred", extra={"track_id": 42, "zone": "press-area"})

    assert log_file.is_file()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["level"] == "INFO"
    assert data["message"] == "Test event occurred"
    assert data["track_id"] == 42
    assert data["zone"] == "press-area"
    assert "ts" in data
