"""Response-time logging middleware.

Logs one record per request with structured extras (`method`, `path`, `status`,
`response_ms`) so p50/p95/p99 can be computed from JSON logs in production or
grepped from text logs in dev. Adds `X-Response-Time-ms` on every response for
on-demand client-side inspection.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("fnu.timing")


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
        logger.info(
            "request method=%s path=%s status=%d response_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "response_ms": round(elapsed_ms, 1),
            },
        )
        return response
