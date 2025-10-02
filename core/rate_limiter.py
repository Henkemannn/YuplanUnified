"""Define a typed RateLimiter Protocol (allow/retry_after) and a factory that selects redis or noop via env. No Any, strict mypy."""
from __future__ import annotations

import os
import time
from typing import Protocol, runtime_checkable

class RateLimitError(Exception):
    """Raised when a request exceeds the configured rate limit.

    Attributes:
        retry_after: Seconds until next permitted attempt.
        limit: Optional symbolic limit name.
    """
    def __init__(self, message: str, retry_after: int, limit: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.limit = limit

@runtime_checkable
class RateLimiter(Protocol):
    def allow(self, key: str, quota: int, per_seconds: int) -> bool: ...  # pragma: no cover
    def retry_after(self, key: str, per_seconds: int) -> int: ...  # pragma: no cover

class _EnvConfig:
    backend: str
    redis_url: str | None
    prefix: str
    def __init__(self) -> None:
        self.reload()
    def reload(self) -> None:
        self.backend = os.getenv("RATE_LIMIT_BACKEND", "noop").strip().lower() or "noop"
        self.redis_url = os.getenv("REDIS_URL")
        self.prefix = os.getenv("RATE_LIMIT_PREFIX", "yuplan:rl:")

_cfg = _EnvConfig()

# Lazy singletons
_instance: RateLimiter | None = None

class BackendInitError(Exception):
    pass

def _build() -> RateLimiter:
    if _cfg.backend == "memory":  # simple in-process fixed window backend (testing)
        from .rate_limiter_memory import MemoryRateLimiter  # type: ignore
        return MemoryRateLimiter()
    if _cfg.backend == "redis":
        try:
            from .rate_limiter_redis import RedisRateLimiter  # local import to keep optional dependency boundary
            return RedisRateLimiter(_cfg.redis_url or "redis://localhost:6379/0", _cfg.prefix)
        except Exception:
            # Fallback to noop silently; production logging added in app_factory wiring.
            from .rate_limiter_noop import NoopRateLimiter
            return NoopRateLimiter()
    from .rate_limiter_noop import NoopRateLimiter
    return NoopRateLimiter()

def get_rate_limiter() -> RateLimiter:
    global _instance
    if _instance is None:
        _instance = _build()
    return _instance

# Test helper to force rebuild after env var changes.
def _test_reset() -> None:  # pragma: no cover - invoked by tests explicitly
    global _instance
    _cfg.reload()
    _instance = None

# Simple utility for fixed-window partitioning reused by redis fallback tests

def window_start(epoch: float | None = None, size: int = 60) -> int:
    """Return the epoch second representing the window bucket start."""
    e = int(epoch if epoch is not None else time.time())
    return e - (e % size)

__all__ = [
    "RateLimiter",
    "RateLimitError",
    "get_rate_limiter",
    "window_start",
]
