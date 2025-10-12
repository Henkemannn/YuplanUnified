"""Noop backend – always allows."""

from __future__ import annotations

from .rate_limiter import RateLimiter


class NoopRateLimiter(RateLimiter):  # type: ignore[misc]
    def allow(self, key: str, quota: int, per_seconds: int) -> bool:  # noqa: D401
        return True

    def retry_after(self, key: str, per_seconds: int) -> int:  # noqa: D401
        return 0


__all__ = ["NoopRateLimiter"]
