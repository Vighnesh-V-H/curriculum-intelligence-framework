import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

from app.api.errors import register_exception_handlers
from app.api.middleware import RequestLoggingMiddleware
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging, safe_exception_details
from app.db.bootstrap import bootstrap_admin

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Application startup began",
        extra={"app_name": settings.app_name, "environment": settings.environment},
    )
    if settings.neo4j_uri:
        auth = None
        if settings.neo4j_password:
            auth = (settings.neo4j_username, settings.neo4j_password.get_secret_value())
        app.state.neo4j_driver = GraphDatabase.driver(settings.neo4j_uri, auth=auth)
    else:
        app.state.neo4j_driver = None
    try:
        bootstrap_admin()
    except Exception as exc:
        logger.error(
            "Application startup failed",
            extra={
                "app_name": settings.app_name,
                "environment": settings.environment,
                **safe_exception_details(exc),
            },
        )
        raise
    logger.info(
        "Application startup completed",
        extra={"app_name": settings.app_name, "environment": settings.environment},
    )
    yield
    if app.state.neo4j_driver is not None:
        app.state.neo4j_driver.close()
    logger.info(
        "Application shutdown",
        extra={"app_name": settings.app_name, "environment": settings.environment},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        expose_headers=["X-Request-ID"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    application.add_middleware(RequestLoggingMiddleware)

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
