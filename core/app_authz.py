"""Pocket 6 - Authorization helpers.

Copilot prompt: Refactor require_roles(*roles) to raise AuthzError(403) with required_role (canonical) instead of returning a Response. Map RoleLike→Canonical via roles.to_canonical. Remove Response unions.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar, cast

from .app_sessions import SessionData, get_session
from .roles import CanonicalRole, RoleLike, to_canonical

P = ParamSpec("P")
R = TypeVar("R")


def enforce_tenant(resource_tenant_id: int, sess: SessionData) -> None:
    if resource_tenant_id != sess["tenant_id"]:
        # Raise standard authorization error; central handler maps to 403
        raise AuthzError("tenant mismatch")


def can_modify(role: str) -> bool:
    # Accept dynamic str (e.g., from session) and cast to RoleLike for mapping
    return to_canonical(cast(RoleLike, role)) in ("superuser", "admin", "editor")


class AuthzError(Exception):
    """Signals an authorization (403) failure to be optionally caught by centralized handlers."""

    required: CanonicalRole | None

    def __init__(self, message: str = "forbidden", required: CanonicalRole | None = None):
        super().__init__(message)
        self.required = required


def require_roles(*roles: RoleLike) -> Callable[[Callable[P, R]], Callable[P, R]]:
    canonical_allowed = [to_canonical(r) for r in roles]

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs):  # type: ignore[no-untyped-def]
            sess = get_session()
            if sess is None:
                # No session -> unauthorized
                from .app_sessions import SessionError  # local import to avoid cycle

                raise SessionError("authentication required")
            role_value = to_canonical(cast(RoleLike, sess["role"]))
            if role_value not in canonical_allowed:
                # Raise with first required canonical role for enriched handler output
                req = canonical_allowed[0] if canonical_allowed else None
                from typing import cast as _cast

                raise AuthzError("forbidden", required=_cast(CanonicalRole | None, req))
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "require_roles",
    "can_modify",
    "enforce_tenant",
    "AuthzError",
]
