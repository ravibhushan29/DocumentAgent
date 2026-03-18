"""FastAPI app factory, lifespan, middleware, router mount (Section 12)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.api.v1 import api_router
from app.core.exceptions import DocAgentError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware, TimingMiddleware, add_cors_middleware
from app.core.tracing import setup_tracing

# Import models so Base.metadata is populated for migrations
from app.models import Base, Document, DocumentChunk, Organisation, User  # noqa: F401

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: configure logging, tracing. Shutdown: cleanup."""
    configure_logging()
    setup_tracing(app)
    yield
    # Shutdown: close pools etc. if needed
    return


def create_app() -> FastAPI:
    app = FastAPI(
        title="DocAgent API",
        description="Enterprise Document AI Agent — document upload, ingestion, and chat",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware order: last added = first executed (so CORS runs first when responding)
    add_cors_middleware(app)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Mount API router
    app.include_router(api_router)

    # Prometheus /metrics (internal only in prod)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Global exception handler for DocAgentError
    @app.exception_handler(DocAgentError)
    async def doc_agent_exception_handler(request: Request, exc: DocAgentError) -> JSONResponse:
        logger.warning(
            "domain_error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "code": exc.error_code,
                **exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
        )

    return app


app = create_app()
