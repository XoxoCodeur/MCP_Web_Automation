"""
Logging configuration for the MCP web automation server.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict

try:
    import orjson

    def _json_dumps(payload: Dict[str, Any]) -> str:
        return orjson.dumps(payload).decode("utf-8")

except ImportError:  # pragma: no cover - fallback path

    def _json_dumps(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class JsonFormatter(logging.Formatter):
    """Turn log records into structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        # Merge context provided via `extra`
        if record.__dict__:
            for key, value in record.__dict__.items():
                if key.startswith("_"):
                    continue
                if key in {"name", "msg", "args", "levelno", "levelname", "pathname", "filename",
                           "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                           "created", "msecs", "relativeCreated", "thread", "threadName",
                           "processName", "process"}:
                    continue
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return _json_dumps(payload)


def configure_logging(default_level: int = logging.INFO) -> None:
    """
    Configure a JSON logger that writes to stderr (to keep stdout clean for MCP).
    """

    if getattr(configure_logging, "_configured", False):
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(default_level)
    # Remove any pre-existing handlers installed by the host environment.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    configure_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
