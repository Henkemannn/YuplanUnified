from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from typing import Any

from flask import g, has_request_context, session

from .limit_registry import get_limit
from .metrics import increment as metrics_increment
from .rate_limiter import RateLimitError, TokenBucketRateLimiter, get_rate_limiter

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
    quota: int | None = None,
    per_seconds: int | None = None,
    key_func: LimiterKeyFunc = _DEF_KEY,
    feature_flag: str | None = None,
    flag_opt_in: bool = True,
    use_registry: bool = True,
):
    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            # Feature flag gating: if flag provided and not enabled for tenant → bypass
            if feature_flag and has_request_context():
                from flask import current_app as _ca, g as _g

                flags = getattr(_g, "tenant_feature_flags", {})
                enabled_val = flags.get(feature_flag)
                if enabled_val is None:
                    # fallback to global FEATURE_FLAGS config for dark launch
                    cfg_flags = _ca.config.get("FEATURE_FLAGS") or {}
                    enabled_val = cfg_flags.get(feature_flag)
                enabled = bool(enabled_val)
                if flag_opt_in and not enabled:
                    return fn(*args, **kwargs)

            # Resolve quota/per via registry if not explicitly provided
            q = quota
            p = per_seconds
            burst: int | None = None
            strategy: str | None = None
            if use_registry and (q is None or p is None or burst is None or strategy is None):
                # Prefer explicit tenant_id from session if available
                tenant_id = 0
                with suppress(Exception):
                    tval = session.get("tenant_id") if has_request_context() else None
                    if isinstance(tval, int):
                        tenant_id = tval
                    elif isinstance(tval, str) and tval.isdigit():
                        tenant_id = int(tval)
                ld, _src = get_limit(tenant_id, name)
                if q is None:
                    q = int(ld.get("quota", 1))  # type: ignore[arg-type]
                if p is None:
                    p = int(ld.get("per_seconds", 60))  # type: ignore[arg-type]
                # Optional fields
                with suppress(Exception):
                    burst = int(ld.get("burst", q))  # type: ignore[arg-type]
                strategy = ld.get("strategy")  # type: ignore[assignment]
            if q is None or p is None:  # final guard
                q = 1
                p = 60
            if burst is None:
                burst = q
            # Resolve strategy (env default RATE_LIMIT_ALGO else "fixed")
            env_default = os.getenv("RATE_LIMIT_ALGO", "fixed").strip().lower() or "fixed"
            if strategy not in ("fixed", "token_bucket"):
                strategy = env_default if env_default in ("fixed", "token_bucket") else "fixed"
            key_val = key_func()
            logical_key = f"{name}:{key_val}"
            rl = get_rate_limiter("token_bucket" if strategy == "token_bucket" else "fixed")
            # If token bucket and backend supports extended interface, use it; else fallback to standard allow.
            if strategy == "token_bucket" and isinstance(rl, TokenBucketRateLimiter):  # type: ignore[arg-type]
                try:
                    allowed = rl.allow_bucket(logical_key, quota=q, per_seconds=p, burst=burst)  # type: ignore[attr-defined]
                except Exception:
                    allowed = rl.allow(logical_key, quota=q, per_seconds=p)
            else:
                allowed = rl.allow(logical_key, quota=q, per_seconds=p)
            outcome = "allow" if allowed else "block"
            with suppress(Exception):  # pragma: no cover - metrics must not break request
                metrics_increment(
                    "rate_limit.hit",
                    {"name": name, "outcome": outcome, "window": str(p), "strategy": strategy},
                )
            if not allowed:
                # Retry-after: attempt token bucket variant
                retry_after = rl.retry_after(logical_key, per_seconds=p)
                if strategy == "token_bucket" and isinstance(rl, TokenBucketRateLimiter):  # type: ignore[arg-type]
                    with suppress(Exception):
                        retry_after = rl.retry_after_bucket(
                            logical_key, quota=q, per_seconds=p, burst=burst
                        )  # type: ignore[attr-defined]
                raise RateLimitError(
                    f"Rate limit exceeded for {name}", retry_after=retry_after, limit=name
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["limit"]
