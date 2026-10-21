"""HTTP request timing and access logs."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("openrecognition.request")

_SKIP_PATH_PREFIXES = ("/assets/",)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, and duration for API requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path.startswith(_SKIP_PATH_PREFIXES):
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "HTTP %s %s -> error (%.0f ms)",
                request.method,
                path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        logger.info(
            "HTTP %s %s -> %s (%.0f ms)",
            request.method,
            path,
            status_code,
            elapsed_ms,
        )
        return response
