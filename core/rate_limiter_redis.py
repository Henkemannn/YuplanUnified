"""Implement fixed-window limiter using Redis INCR+EXPIRE (set EXPIRE when INCR==1). Provide retry_after via TTL. Handle connection errors by raising a specific BackendInitError."""
from __future__ import annotations

import time
from typing import Final

try:
    import redis  # type: ignore
except Exception as e:  # pragma: no cover
    redis = None  # type: ignore

from .rate_limiter import RateLimiter, window_start

class RedisRateLimiter(RateLimiter):  # type: ignore[misc]
    _PREFIX: str
    _client: "redis.Redis"  # type: ignore[name-defined]
    def __init__(self, url: str, prefix: str) -> None:
        if redis is None:
            raise RuntimeError("redis library not available")
        self._client = redis.Redis.from_url(url, decode_responses=False)
        self._PREFIX = prefix

    def _key(self, logical_key: str, per_seconds: int) -> str:
        ws = window_start(size=per_seconds)
        return f"{self._PREFIX}{logical_key}:{ws}:{per_seconds}"

    def allow(self, key: str, quota: int, per_seconds: int) -> bool:
        rk = self._key(key, per_seconds)
        pipe = self._client.pipeline(transaction=True)
        pipe.incr(rk, 1)
        pipe.ttl(rk)
        results = pipe.execute()
        count = int(results[0])
        ttl = int(results[1])
        if count == 1 or ttl < 0:
            # first increment or no ttl yet -> set expire
            self._client.expire(rk, per_seconds)
        return count <= quota

    def retry_after(self, key: str, per_seconds: int) -> int:
        rk = self._key(key, per_seconds)
        ttl = self._client.ttl(rk)
        if ttl is None or ttl < 0:
            return per_seconds
        return int(ttl)

__all__ = ["RedisRateLimiter"]
