"""In-process token bucket rate limiter (memory backend).

Not for production multi-process use; intended for tests and as fallback when Redis
backend is unavailable. Provides fairness vs fixed window.

Algorithm:
- State per key: tokens (float), last_refill (epoch seconds)
- Refill on each allow():
    elapsed = now - last_refill
    tokens = min(capacity, tokens + elapsed * refill_rate)
- If tokens >= 1: consume 1, allow.
  Else: block, retry_after = ceil((1 - tokens)/refill_rate)

Burst capacity defaults to quota if not explicitly provided to allow a full window burst.

Time function is injectable for deterministic tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .rate_limiter import RateLimiter

TimeFn = Callable[[], float]


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class MemoryTokenBucketRateLimiter(RateLimiter):
    def __init__(self, now_func: TimeFn | None = None) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._now: TimeFn = now_func or time.time

    # We extend the protocol conceptually with burst (capacity). Existing allow signature does not expose burst.
    # To integrate minimally we allow callers to encode capacity inside key name when needed, but for HTTP integration
    # we will adapt code to provide a token-bucket specific path. For initial scaffold we accept standard signature
    # and treat quota as both steady rate and capacity; later integration layer will pass burst via a prefixed key.
    def allow(
        self, key: str, quota: int, per_seconds: int
    ) -> bool:  # uses quota as both rate & capacity
        capacity = quota
        refill_rate = quota / per_seconds  # tokens per second
        now = self._now()
        b = self._buckets.get(key)
        if b is None:
            self._buckets[key] = _Bucket(tokens=float(capacity - 1), last_refill=now)
            return True
        # Refill
        if now > b.last_refill:
            elapsed = now - b.last_refill
            new_tokens = min(capacity, b.tokens + elapsed * refill_rate)
            b.tokens = new_tokens
            b.last_refill = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True
        # Not enough tokens
        return False

    def retry_after(self, key: str, per_seconds: int) -> int:
        b = self._buckets.get(key)
        if b is None:
            return 0
        # We do not know quota directly (steady rate) here; approximate using observed refill by storing rate in key not implemented yet.
        # For memory backend tests we will embed rate info into key as key|quota|per, but keep simple fallback for now.
        # Without rate info, fall back to 1 second.
        return 1


__all__ = ["MemoryTokenBucketRateLimiter"]
