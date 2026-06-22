"""Structured JSON logging for Cloud Logging compatibility.

Cloud Logging parses jsonPayload automatically when the log line is valid JSON.
Fields like transfer_id, status, and severity become queryable in Log Explorer
and can drive log-based metrics in Cloud Monitoring.

Usage:
    from .logging_config import get_logger
    log = get_logger(__name__)
    log.info("transfer queued", transfer_id=tid, file_id=fid)
"""
import json
import logging
import sys
from typing import Any


class _StructuredFormatter(logging.Formatter):
    SEVERITY = {
        logging.DEBUG:    "DEBUG",
        logging.INFO:     "INFO",
        logging.WARNING:  "WARNING",
        logging.ERROR:    "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": self.SEVERITY.get(record.levelno, "DEFAULT"),
            "message":  record.getMessage(),
            "logger":   record.name,
        }
        # Merge any extra fields passed via log.info("msg", extra={...})
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            }:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> "StructuredLogger":
    return StructuredLogger(logging.getLogger(name))


class StructuredLogger:
    """Thin wrapper that accepts keyword args as structured fields."""

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    def _emit(self, level: int, message: str, **fields: Any) -> None:
        self._log.log(level, message, extra=fields)

    def debug(self, msg: str, **kw: Any)    -> None: self._emit(logging.DEBUG,    msg, **kw)
    def info(self, msg: str, **kw: Any)     -> None: self._emit(logging.INFO,     msg, **kw)
    def warning(self, msg: str, **kw: Any)  -> None: self._emit(logging.WARNING,  msg, **kw)
    def error(self, msg: str, **kw: Any)    -> None: self._emit(logging.ERROR,    msg, **kw)
    def critical(self, msg: str, **kw: Any) -> None: self._emit(logging.CRITICAL, msg, **kw)
