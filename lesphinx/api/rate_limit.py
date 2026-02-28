"""Simple in-memory rate limiter middleware (sliding window per IP)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

WINDOW_SECONDS = 60
MAX_REQUESTS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits each client IP to MAX_REQUESTS per WINDOW_SECONDS."""

    def __init__(self, app, window: int = WINDOW_SECONDS, max_requests: int = MAX_REQUESTS) -> None:
        super().__init__(app)
        self.window = window
        self.max_requests = max_requests
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window

        timestamps = self._hits[client_ip]
        self._hits[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._hits[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests, please slow down"},
            )

        self._hits[client_ip].append(now)
        return await call_next(request)
