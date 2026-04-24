"""Logging configuration.

Default text format is a compact, greppable `key=value` line for dev. Setting
`LOG_FORMAT=json` (used by `docker-compose.prod.yml`) switches every handler to
newline-delimited JSON so the production log shipper (Loki, CloudWatch, etc.)
can parse the full record and the reserved fields (method, path, status,
response_ms) added by ResponseTimeMiddleware.

PII hygiene: handlers intentionally do not log request bodies or response
bodies. Structured extras added by the middleware contain only the request
line metadata.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

RESERVED_ATTRS = {
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
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Newline-delimited JSON records for production log shippers."""

    def format(self, record: logging.LogRecord) -> str:
        from datetime import UTC, datetime

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Structured extras passed as `logger.info(msg, extra={...})`.
        for key, value in record.__dict__.items():
            if key in RESERVED_ATTRS or key.startswith("_"):
                continue
            # Skip the formatter-held default attrs we already serialised.
            if key in payload:
                continue
            payload[key] = value

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    """Idempotent top-level logging setup.

    Honours `LOG_LEVEL` (default `INFO`) and `LOG_FORMAT` (`text` | `json`,
    default `text`). Called from main.py at import time.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(stream=sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    # Replace handlers so re-import (e.g. under uvicorn --reload) stays clean.
    root.handlers = [handler]
    root.setLevel(level)

    # Keep uvicorn access logging aligned with our format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(level)
