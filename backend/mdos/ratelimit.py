"""Small in-memory sliding-window rate limiter.

Good enough for the desktop build and a single cloud instance. A multi-instance deployment should
replace the store with Redis (see docs/13-deployment.md).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from .config import get_settings
from .errors import RateLimited


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = max(1, int(window_seconds - (now - q[0])))
                raise RateLimited(
                    "Too many requests. Please wait and try again.", details={"retry_after_seconds": retry}
                )
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_auth(request: Request) -> None:
    limiter.hit(f"auth:{_client_key(request)}", get_settings().rate_limit_auth_per_minute)


def limit_agents(request: Request) -> None:
    limiter.hit(f"agents:{_client_key(request)}", get_settings().rate_limit_agents_per_minute)


def limit_uploads(request: Request) -> None:
    limiter.hit(f"uploads:{_client_key(request)}", get_settings().rate_limit_uploads_per_minute)
