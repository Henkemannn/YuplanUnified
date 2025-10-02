from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from typing import Any

from flask import g, has_request_context

from .metrics import increment as metrics_increment
from .rate_limiter import RateLimitError, get_rate_limiter

"""HTTP rate limiting decorator.

Add @limit to a view to enforce fixed-window quotas.
Feature flag gating (opt-in) allows dark launch.
"""

LimiterKeyFunc = Callable[[], str]

def _DEF_KEY() -> str:  # default key uses tenant if present else global bucket
    return getattr(g, "tenant_id", "global")


def limit(
    name: str,
    *,
    quota: int,
    per_seconds: int,
    key_func: LimiterKeyFunc = _DEF_KEY,
    feature_flag: str | None = None,
    flag_opt_in: bool = True,
):

    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            # Feature flag gating: if flag provided and not enabled for tenant → bypass
            if feature_flag and has_request_context():
                from flask import g as _g
                flags = getattr(_g, "tenant_feature_flags", {})
                enabled = bool(flags.get(feature_flag))
                # If opt-in, we only enforce when tenant flag explicitly true.
                if flag_opt_in and not enabled:
                    return fn(*args, **kwargs)

            key_val = key_func()
            logical_key = f"{name}:{key_val}"
            rl = get_rate_limiter()
            allowed = rl.allow(logical_key, quota=quota, per_seconds=per_seconds)
            outcome = "allow" if allowed else "block"
            with suppress(Exception):  # pragma: no cover - metrics must not break request
                metrics_increment(
                    "rate_limit.hit",
                    {"name": name, "outcome": outcome, "window": str(per_seconds)},
                )
            if not allowed:
                raise RateLimitError(
                    f"Rate limit exceeded for {name}",
                    retry_after=rl.retry_after(logical_key, per_seconds=per_seconds),
                    limit=name,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator

__all__ = ["limit"]
