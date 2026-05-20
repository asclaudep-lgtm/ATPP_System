"""Centralized logging for ATPP System.

Replaces ad-hoc ``print()`` calls with structured logging.
Usage::

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("message")
    log.warning("something", extra={"user_id": 1})
"""
import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_INITIALIZED = False


class JsonFormatter(logging.Formatter):
    """JSON-structured log formatter for machine consumption."""

    def format(self, record):
        obj = {
            "ts": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            obj["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k not in ('msg', 'args', 'created', 'filename',
                         'funcName', 'levelname', 'levelno',
                         'lineno', 'module', 'msecs', 'name',
                         'pathname', 'process', 'processName',
                         'relativeCreated', 'thread', 'threadName',
                         'exc_info', 'exc_text', 'stack_info'):
                obj[k] = v
        return json.dumps(obj, ensure_ascii=False, default=str)


def setup_logging(log_level: str = "INFO", log_file: str | None = None,
                  json_format: bool = False):
    """Configure root logger with console + rotating file handler.

    Called once at startup. Subsequent calls are no-ops.

    Args:
        log_level: DEBUG, INFO, WARNING, ERROR
        log_file: path to log file (rotates at 10 MB, 5 backups)
        json_format: if True, use JSON-structured format for log files
    """
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return
    _LOG_INITIALIZED = True

    root = logging.getLogger("atpp")
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if json_format:
        fmt = JsonFormatter()
    else:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler (10 MB x 5 backups)
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, encoding="utf-8",
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
            )
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except OSError:
            root.warning("Cannot write to log file: %s", log_file)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of 'atpp'."""
    return logging.getLogger(f"atpp.{name}")
