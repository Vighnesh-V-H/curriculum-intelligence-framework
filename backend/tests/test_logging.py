import json
import logging
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.api.middleware import RequestLoggingMiddleware
from app.core.logging_config import JsonLogFormatter, safe_exception_details


def test_json_formatter_includes_only_approved_fields():
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "trace-123"
    record.status_code = 200
    record.authorization = "Bearer do-not-log"
    record.password = "do-not-log"

    formatted = JsonLogFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["message"] == "request completed"
    assert payload["request_id"] == "trace-123"
    assert payload["status_code"] == 200
    assert "authorization" not in payload
    assert "password" not in payload
    assert "do-not-log" not in formatted


def test_json_formatter_omits_exception_message():
    try:
        raise ValueError("sensitive exception detail")
    except ValueError as exc:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="operation failed",
            args=(),
            exc_info=None,
        )
        for name, value in safe_exception_details(exc).items():
            setattr(record, name, value)

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["exception_type"] == "ValueError"
    assert payload["stacktrace"]
    assert "sensitive exception detail" not in json.dumps(payload)
    assert "sensitive exception detail" not in logging.Formatter().format(record)


def test_request_log_has_correlation_id_and_safe_route(client, caplog):
    caplog.set_level(logging.INFO, logger="app.api.middleware")
    response = client.get(
        "/health?access_token=never-log-this",
        headers={"X-Request-ID": "trace-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-123"
    request_log = next(
        record for record in caplog.records if record.getMessage() == "HTTP request completed"
    )
    assert request_log.request_id == "trace-123"
    assert request_log.route == "/health"
    assert request_log.status_code == 200
    assert "access_token" not in request_log.getMessage()


def test_invalid_request_id_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "unsafe/id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe/id"
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])


def test_unhandled_error_is_redacted_and_returns_request_id(caplog):
    application = FastAPI()
    register_exception_handlers(application)
    application.add_middleware(RequestLoggingMiddleware)

    @application.get("/explode/{item_id}")
    def explode(item_id: str):
        raise RuntimeError(f"sensitive detail {item_id}")

    caplog.set_level(logging.INFO, logger="app")
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/explode/private-value", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-500"
    assert response.json()["error"]["code"] == "internal_server_error"
    assert "private-value" not in caplog.text
    error_log = next(
        record for record in caplog.records if record.getMessage() == "Unhandled request exception"
    )
    assert error_log.exception_type == "RuntimeError"
    assert error_log.stacktrace


def test_failed_login_log_does_not_include_credentials(client, caplog):
    caplog.set_level(logging.INFO, logger="app")
    username = "private-user@example.com"
    password = "private-password-value"

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )

    assert response.status_code == 401
    assert username not in caplog.text
    assert password not in caplog.text
    assert any(record.getMessage() == "Login rejected" for record in caplog.records)
