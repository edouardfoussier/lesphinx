"""Simple in-memory rate limiter middleware (sliding window per IP)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

WINDOW_SECONDS = 60
MAX_REQUESTS = 60
MAX_TRACKED_IPS = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits each client IP to MAX_REQUESTS per WINDOW_SECONDS.

    Evicts stale IPs when the tracking map exceeds MAX_TRACKED_IPS to
    prevent unbounded memory growth.
    """

    def __init__(
        self,
        app,
        window: int = WINDOW_SECONDS,
        max_requests: int = MAX_REQUESTS,
        max_tracked_ips: int = MAX_TRACKED_IPS,
    ) -> None:
        super().__init__(app)
        self.window = window
        self.max_requests = max_requests
        self.max_tracked_ips = max_tracked_ips
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_eviction: float = 0.0

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window

        # Prune this IP's expired timestamps
        timestamps = self._hits[client_ip]
        self._hits[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._hits[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests, please slow down"},
            )

        self._hits[client_ip].append(now)

        # Periodic global eviction (at most once per window)
        if len(self._hits) > self.max_tracked_ips or now - self._last_eviction > self.window:
            self._evict_stale(cutoff)
            self._last_eviction = now

        return await call_next(request)

    def _evict_stale(self, cutoff: float) -> None:
        stale = [ip for ip, ts in self._hits.items() if not ts or ts[-1] <= cutoff]
        for ip in stale:
            del self._hits[ip]
