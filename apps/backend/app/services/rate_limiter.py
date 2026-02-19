from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import time


class RateLimitExceeded(RuntimeError):
    pass


class RateLimiterService:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time()
        start = now - window_seconds

        with self._lock:
            q = self._events[key]
            while q and q[0] < start:
                q.popleft()

            if len(q) >= limit:
                raise RateLimitExceeded(f"Rate limit exceeded for key={key}")

            q.append(now)


rate_limiter_service = RateLimiterService()
