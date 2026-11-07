"""Application logging configuration and request-scoped log context."""

from __future__ import annotations

import json
import logging
import logging.config
import traceback
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("actor_id", default=None)

_LOG_FIELDS = (
    "request_id",
    "actor_id",
    "target_user_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "error_code",
    "error_count",
    "error_types",
    "file_count",
    "file_size_bytes",
    "text_chars",
    "semester_count",
    "course_count",
    "peo_count",
    "po_count",
    "mapping_count",
    "document_id",
    "document_status",
    "verification_run_id",
    "finding_count",
    "provider_status",
    "attempt",
    "max_attempts",
    "model",
    "operation",
    "exception_type",
    "stacktrace",
    "app_name",
    "environment",
)


class RequestContextFilter(logging.Filter):
    """Attach request context without requiring every call site to pass it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id.get()
        if not hasattr(record, "actor_id"):
            record.actor_id = _actor_id.get()
        return True


class JsonLogFormatter(logging.Formatter):
    """Emit one structured JSON object per log event, omitting unsafe extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            exception_type, _exception, exception_traceback = record.exc_info
            payload["exception"] = {
                "type": exception_type.__name__ if exception_type else "Exception",
                # Keep useful stack locations, but intentionally omit exception text.
                "stacktrace": [
                    f"{frame.filename}:{frame.lineno} in {frame.name}"
                    for frame in traceback.extract_tb(exception_traceback)
                ],
            }
        return json.dumps(payload, ensure_ascii=False, default=str)


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def set_actor_id(actor_id: str) -> None:
    _actor_id.set(actor_id)


def reset_request_context(token: Token[str | None]) -> None:
    _actor_id.set(None)
    _request_id.reset(token)


def safe_exception_details(exception: BaseException) -> dict[str, Any]:
    """Return exception type and frame locations without exception/source text."""
    return {
        "exception_type": type(exception).__name__,
        "stacktrace": [
            f"{frame.filename}:{frame.lineno} in {frame.name}"
            for frame in traceback.extract_tb(exception.__traceback__)
        ],
    }


def configure_logging(level: str = "INFO") -> None:
    """Configure console-only structured logging for the app and Uvicorn."""
    normalized_level = level.upper()
    if normalized_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        normalized_level = "INFO"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {
                    "()": "app.core.logging_config.RequestContextFilter",
                },
            },
            "formatters": {
                "json": {"()": "app.core.logging_config.JsonLogFormatter"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                    "filters": ["request_context"],
                },
                "discard_access": {"class": "logging.NullHandler"},
            },
            "loggers": {
                "app": {"level": normalized_level, "propagate": True},
                "uvicorn": {"level": normalized_level, "propagate": True},
                "uvicorn.access": {
                    "handlers": ["discard_access"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "httpx": {"level": "WARNING", "propagate": True},
                "httpcore": {"level": "WARNING", "propagate": True},
                "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
            },
            "root": {"handlers": ["console"], "level": normalized_level},
        }
    )
