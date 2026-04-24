"""Tests for logging_config — Part 16."""

from __future__ import annotations

import json
import logging

import pytest

from src.backend.logging_config import JsonFormatter, configure_logging


def _make_record(extra: dict[str, object] | None = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="fnu.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_structured_extras() -> None:
    formatter = JsonFormatter()
    record = _make_record(
        {"method": "GET", "path": "/foo", "status": 200, "response_ms": 12.3}
    )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "fnu.test"
    assert payload["message"] == "hello world"
    assert payload["method"] == "GET"
    assert payload["path"] == "/foo"
    assert payload["status"] == 200
    assert payload["response_ms"] == 12.3
    assert "timestamp" in payload and "T" in payload["timestamp"]


def test_json_formatter_skips_reserved_attrs() -> None:
    formatter = JsonFormatter()
    record = _make_record({"pathname": "/should/not/leak"})
    payload = json.loads(formatter.format(record))
    assert "pathname" not in payload  # RESERVED_ATTRS filter keeps logger output tidy


def test_json_formatter_captures_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            name="fnu.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "ERROR"
    assert "RuntimeError: boom" in payload["exception"]


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_configure_logging_respects_log_format(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    monkeypatch.setenv("LOG_FORMAT", fmt)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    if fmt == "json":
        assert isinstance(handler.formatter, JsonFormatter)
    else:
        assert not isinstance(handler.formatter, JsonFormatter)
