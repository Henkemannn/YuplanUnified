"""In-process memory fixed-window rate limiter for tests.
Not for production (single-process only)."""
from __future__ import annotations
import time
from typing import Dict, Tuple

from .rate_limiter import RateLimiter, window_start

class MemoryRateLimiter(RateLimiter):  # type: ignore[misc]
    def __init__(self) -> None:
        # key -> (window_start, count)
        self._buckets: Dict[str, Tuple[int,int]] = {}

    def allow(self, key: str, quota: int, per_seconds: int) -> bool:
        ws = window_start(size=per_seconds)
        cur = self._buckets.get(key)
        if cur is None or cur[0] != ws:
            self._buckets[key] = (ws, 1)
            return True
        # same window
        new_count = cur[1] + 1
        self._buckets[key] = (ws, new_count)
        return new_count <= quota

    def retry_after(self, key: str, per_seconds: int) -> int:
        cur = self._buckets.get(key)
        if not cur:
            return 0
        ws, _ = cur
        now = int(time.time())
        end = ws + per_seconds
        if now >= end:
            return 0
        return end - now

__all__ = ["MemoryRateLimiter"]
