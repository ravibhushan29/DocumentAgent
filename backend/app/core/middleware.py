"""RequestID, timing, tracing, CORS middleware (Section 12)."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID (UUID) and bind to structlog context."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Record request duration for metrics (path as label)."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        # Use a generic label; instrumentator adds http_request_duration_seconds
        structlog.contextvars.bind_contextvars(duration_ms=round(duration * 1000))
        return response


def add_cors_middleware(app: object) -> None:
    """Add CORS middleware using settings. Call after creating FastAPI app."""
    from fastapi.middleware.cors import CORSMiddleware

    settings = get_settings()
    app.add_middleware(  # type: ignore[union-attr]
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
