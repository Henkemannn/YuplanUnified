"""Define a typed RateLimiter Protocol (allow/retry_after) and a factory that selects redis or noop via env. No Any, strict mypy."""

from __future__ import annotations

import os
import time
from typing import Literal, Protocol, runtime_checkable


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


# Extended interface for token bucket (duck typed)
@runtime_checkable
class TokenBucketRateLimiter(RateLimiter, Protocol):  # pragma: no cover
    def allow_bucket(self, key: str, quota: int, per_seconds: int, burst: int) -> bool: ...
    def retry_after_bucket(self, key: str, quota: int, per_seconds: int, burst: int) -> int: ...


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
_instance_fixed: RateLimiter | None = None  # fixed-window backend
_instance_tb: RateLimiter | None = None  # token-bucket backend


class BackendInitError(Exception):
    pass


def _build_fixed() -> RateLimiter:
    if _cfg.backend == "memory":  # simple in-process fixed window backend (testing)
        from .rate_limiter_memory import MemoryRateLimiter  # type: ignore

        return MemoryRateLimiter()
    if _cfg.backend == "redis":
        try:
            from .rate_limiter_redis import (
                RedisRateLimiter,  # local import to keep optional dependency boundary
            )

            return RedisRateLimiter(_cfg.redis_url or "redis://localhost:6379/0", _cfg.prefix)
        except Exception:
            # Fallback to noop silently; production logging added in app_factory wiring.
            from .rate_limiter_noop import NoopRateLimiter

            return NoopRateLimiter()
    from .rate_limiter_noop import NoopRateLimiter

    return NoopRateLimiter()


def _build_token_bucket() -> RateLimiter:
    # Choose memory or redis token bucket based on same backend env for consistency; fallback to memory if redis unsupported.
    if _cfg.backend == "redis":
        try:
            from .rate_limiter_token_bucket_redis import RedisTokenBucketRateLimiter  # type: ignore

            return RedisTokenBucketRateLimiter(
                _cfg.redis_url or "redis://localhost:6379/0", _cfg.prefix
            )
        except Exception:
            pass
    # memory fallback
    from .rate_limiter_token_bucket_memory import MemoryTokenBucketRateLimiter  # type: ignore

    return MemoryTokenBucketRateLimiter()


def get_rate_limiter(strategy: Literal["fixed", "token_bucket"] = "fixed") -> RateLimiter:
    global _instance_fixed, _instance_tb
    if strategy == "token_bucket":
        if _instance_tb is None:
            _instance_tb = _build_token_bucket()
        return _instance_tb
    if _instance_fixed is None:
        _instance_fixed = _build_fixed()
    return _instance_fixed


# Test helper to force rebuild after env var changes.
def _test_reset() -> None:  # pragma: no cover - invoked by tests explicitly
    global _instance_fixed, _instance_tb
    _cfg.reload()
    _instance_fixed = None
    _instance_tb = None


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
