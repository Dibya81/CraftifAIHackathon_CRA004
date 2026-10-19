"""Structured logging for SiteSentinel: JSON lines to log file + human-readable console."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Include any custom structured extras attached to the record
        for key, val in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                log_obj[key] = val
        return json.dumps(log_obj)


def setup_logging(
    log_file: str = "logs/sentinel.log",
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configures structured logging for SiteSentinel."""
    logger = logging.getLogger("sentinel")
    logger.setLevel(level)
    logger.handlers.clear()

    # Ensure log file directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler (JSON lines)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Console handler (human-readable)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate console output
    logger.propagate = False
    return logger


def get_logger(name: str = "sentinel") -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)


logger = logging.getLogger("sentinel")
