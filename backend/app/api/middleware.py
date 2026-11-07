"""HTTP request correlation and access logging middleware."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from app.core.logging_config import reset_request_context, set_request_id

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REQUEST_ID_HEADER = b"x-request-id"


def _request_id(scope: dict[str, Any]) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == _REQUEST_ID_HEADER:
            try:
                candidate = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if _REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
            break
    return uuid.uuid4().hex


def _route_template(scope: dict[str, Any]) -> str:
    route = scope.get("route")
    template = getattr(route, "path", None)
    return template if isinstance(template, str) else "unmatched"


class RequestLoggingMiddleware:
    """Log request method, route template, outcome, duration, and correlation ID.

    Request bodies, query strings, headers, and raw unmatched paths are never logged.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        context_token = set_request_id(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _REQUEST_ID_HEADER
                ]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            level = (
                logging.ERROR
                if status_code >= 500
                else logging.WARNING
                if status_code >= 400
                else logging.INFO
            )
            logger.log(
                level,
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "actor_id": scope.get("state", {}).get("actor_id"),
                    "method": scope.get("method"),
                    "route": _route_template(scope),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_context(context_token)
