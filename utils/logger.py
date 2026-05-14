"""Centralized logging for ATPP System.

Replaces ad-hoc ``print()`` calls with structured logging.
Usage::

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("message")
    log.warning("something", extra={"user_id": 1})
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

_LOG_INITIALIZED = False


def setup_logging(log_level: str = "INFO", log_file: str | None = None):
    """Configure root logger with console + optional file handler.

    Called once at startup. Subsequent calls are no-ops.
    """
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return
    _LOG_INITIALIZED = True

    root = logging.getLogger("atpp")
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (rotating by date)
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except OSError:
            root.warning("Cannot write to log file: %s", log_file)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of 'atpp'."""
    return logging.getLogger(f"atpp.{name}")
