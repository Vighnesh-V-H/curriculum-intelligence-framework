import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.logging_config import safe_exception_details

logger = logging.getLogger(__name__)


def _request_log_context(request: Request) -> dict[str, str | None]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "actor_id": getattr(request.state, "actor_id", None),
    }


def _error_body(request: Request, code: str, message: str, details=None) -> dict:
    return {
        "error": {"code": code, "message": message},
        "path": request.url.path,
        "details": details,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.log(
            logging.ERROR if exc.status_code >= 500 else logging.WARNING,
            "Application request failed",
            extra={
                **_request_log_context(request),
                "error_code": exc.code,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        logger.warning(
            "Request validation failed",
            extra={
                **_request_log_context(request),
                "error_code": "validation_error",
                "status_code": 422,
                "error_count": len(errors),
                "error_types": sorted({str(error.get("type", "unknown")) for error in errors}),
            },
        )
        return JSONResponse(
            status_code=422,
            content=_error_body(
                request,
                "validation_error",
                "Request validation failed",
                jsonable_encoder(errors),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(
            "HTTP request rejected",
            extra={
                **_request_log_context(request),
                "error_code": "http_error",
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, "http_error", str(exc.detail)),
            headers={
                **(exc.headers or {}),
                "X-Request-ID": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "Unhandled request exception",
            extra={
                **_request_log_context(request),
                "error_code": "internal_server_error",
                "status_code": 500,
                **safe_exception_details(exc),
            },
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                request,
                "internal_server_error",
                "An unexpected error occurred",
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )
