"""Pocket 6 - Authorization helpers.

Copilot prompt: Refactor require_roles(*roles) to raise AuthzError(403) with
required_role (canonical) instead of returning a Response. Map RoleLike→Canonical
via roles.to_canonical. Remove Response unions.

TODO[P7A-auth-inventory]: Expectations from tests
- RBAC mapping must use canonical roles; `cook->viewer`, `unit_portal->editor`.
- 403 handling should expose `required_role` (canonical) for envelope builders.
- Session absence should raise centralized unauthorized for 401 with problem-details style in non-auth routes.
- Keep compatibility with legacy auth endpoints that use `{ok:false,error,message}`.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar, cast

from .app_sessions import SessionData, get_session
from flask import request, current_app, session
from .auth import _clear_authenticated_session, _load_active_user_by_id, _user_auth_version, _user_must_change_password
from .db import get_session as get_db_session
from .jwt_utils import decode as jwt_decode, JWTError
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
    password_change_exempt_endpoints = {
        "ui.account_page",
        "ui.account_change_password",
        "ui.ui_logout",
        "auth.logout",
    }

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs):  # type: ignore[no-untyped-def]
            # Prefer Bearer Authorization header to infer identity for stateless UI/API access
            sess = get_session()
            try:
                auth_header = request.headers.get("Authorization", "")
                if (sess is None or not sess.get("user_id")) and auth_header.lower().startswith("bearer "):
                    token = auth_header.split(None, 1)[1].strip()
                    # Require configured secret; do not use weak fallback defaults.
                    import os as _os
                    primary = current_app.config.get("JWT_SECRET") or _os.getenv("JWT_SECRET")
                    if not primary:
                        runtime_env = (
                            _os.getenv("DEPLOY_ENV")
                            or _os.getenv("APP_ENV")
                            or _os.getenv("FLASK_ENV")
                            or ""
                        ).lower()
                        if runtime_env not in ("pilot", "prod", "production"):
                            primary = current_app.config.get("SECRET_KEY")
                    if not primary:
                        from .app_sessions import SessionError

                        raise SessionError("authentication required")
                    secrets_list = current_app.config.get("JWT_SECRETS") or []
                    # Loosen validation for UI routes: skip issuer/audience checks
                    payload = jwt_decode(
                        token,
                        secret=primary,
                        secrets_list=secrets_list,
                        leeway=current_app.config.get("JWT_LEEWAY_SECONDS", 60),
                        max_age=current_app.config.get("JWT_MAX_AGE_SECONDS"),
                    )
                    auth_version = payload.get("auth_version")
                    if not isinstance(auth_version, int):
                        raise SessionError("authentication required")
                    # Populate session-like dict for downstream checks
                    session["user_id"] = payload.get("sub")
                    session["role"] = payload.get("role")
                    session["tenant_id"] = payload.get("tenant_id")
                    session["auth_version"] = auth_version
                    # Re-fetch to reflect new values
                    sess = get_session()
            except JWTError:
                # Invalid bearer -> treat as no auth; centralized handler will map to 401
                pass
            if sess is None:
                # No session -> unauthorized
                from .app_sessions import SessionError  # local import to avoid cycle

                raise SessionError("authentication required")
            synthetic_test_identity = bool(current_app.config.get("TESTING")) and bool(
                request.headers.get("X-User-Role")
            )
            if synthetic_test_identity:
                role_value = to_canonical(cast(RoleLike, sess["role"]))
            else:
                db = get_db_session()
                try:
                    active_user = _load_active_user_by_id(db, sess["user_id"])
                finally:
                    db.close()
                active_auth_version = _user_auth_version(active_user)
                if active_user is None or active_auth_version is None or session.get("auth_version") is None:
                    _clear_authenticated_session()
                    from .app_sessions import SessionError  # local import to avoid cycle

                    raise SessionError("authentication required")
                if int(session.get("auth_version")) != active_auth_version:
                    _clear_authenticated_session()
                    from .app_sessions import SessionError  # local import to avoid cycle

                    raise SessionError("authentication required")
                if _user_must_change_password(active_user) and request.endpoint not in password_change_exempt_endpoints:
                    if request.endpoint and request.endpoint.startswith("ui.") and (request.method or "").upper() == "GET":
                        from flask import redirect, url_for

                        return redirect(url_for("ui.account_page"))
                    _clear_authenticated_session()
                    from .app_sessions import SessionError  # local import to avoid cycle

                    raise SessionError("authentication required")
                session["user_id"] = active_user.id
                session["role"] = active_user.role
                session["tenant_id"] = active_user.tenant_id
                session["auth_version"] = active_auth_version
                session["must_change_password"] = _user_must_change_password(active_user)
                role_value = to_canonical(cast(RoleLike, active_user.role))
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
