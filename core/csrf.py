"""Strict CSRF middleware (flag gated).

Design:
- Per-session token stored in session under CSRF_TOKEN (rotated daily).
- Accepted via header X-CSRF-Token or form field csrf_token (POST/PUT/PATCH/DELETE only).
- Exempt paths: /health, /auth/, /metrics, /openapi.json, /superuser/impersonate/, (GET safe methods always exempt).
- Selective blueprint roll-out: we start by enforcing only for diet_api and superuser_impersonation endpoints.
- Failing validation returns RFC7807 problem+json using helpers in http_errors.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, request, session
from werkzeug.wrappers.response import Response

from .http_errors import forbidden as _forbidden

CSRF_SESSION_KEY = "CSRF_TOKEN"
CSRF_ISSUED_AT = "CSRF_TOKEN_ISSUED"
TOKEN_TTL = 24 * 3600  # rotate daily
HEADER_NAME = "X-CSRF-Token"
FORM_FIELD = "csrf_token"

# Endpoint (blueprint) prefixes to enforce (incremental rollout)
ENFORCED_PREFIXES = [
    "/diet/",
    "/api/superuser/",
]

EXEMPT_PREFIXES = [
    "/health",
    "/auth/",
    "/metrics",
    "/openapi.json",
]
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _problem_missing() -> Response:
    return _forbidden("csrf_missing", problem_type="https://example.com/problems/csrf_missing")


def _problem_invalid() -> Response:
    return _forbidden("csrf_invalid", problem_type="https://example.com/problems/csrf_invalid")


def generate_token(force: bool = False) -> str:
    now = int(time.time())
    tok = session.get(CSRF_SESSION_KEY)
    issued = int(session.get(CSRF_ISSUED_AT) or 0)
    if force or not tok or (now - issued) > TOKEN_TTL:
        tok = secrets.token_hex(20)
        session[CSRF_SESSION_KEY] = tok
        session[CSRF_ISSUED_AT] = now
    return str(tok)


def validate_token() -> bool:
    # Only consider enforced prefixes to reduce initial migration surface
    path = request.path or "/"
    if not any(path.startswith(p) for p in ENFORCED_PREFIXES):
        return True
    # If superuser missing impersonation on /diet/ writes, allow request to reach app logic so it returns impersonation_required
    try:
        if session.get("role") == "superuser" and path.startswith("/diet/"):
            from .impersonation import get_impersonation  # local import

            if not get_impersonation():
                return True
    except Exception:  # pragma: no cover
        pass
    if request.method.upper() in SAFE_METHODS:
        return True
    if any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return True
    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        return False
    supplied = request.headers.get(HEADER_NAME) or request.form.get(FORM_FIELD)
    if not supplied:
        return False
    try:
        return secrets.compare_digest(str(expected), str(supplied))
    except Exception:
        return False


def csrf_protect(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*a: Any, **kw: Any) -> Any:
        if not validate_token():
            return (
                _problem_invalid()
                if request.headers.get(HEADER_NAME) or request.form.get(FORM_FIELD)
                else _problem_missing()
            )
        return fn(*a, **kw)

    return wrapper


def before_request() -> Response | None:  # to be registered only when flag active
    # Always ensure token exists for session (safe to do on every request)
    g.csrf_token = generate_token()
    method = request.method.upper()
    if method in SAFE_METHODS:
        return None
    path = request.path or "/"
    if any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return None
    if not any(path.startswith(p) for p in ENFORCED_PREFIXES):
        return None
    if not validate_token():
        # Distinguish missing vs invalid
        return (
            _problem_invalid()
            if (request.headers.get(HEADER_NAME) or request.form.get(FORM_FIELD))
            else _problem_missing()
        )
    return None


__all__ = [
    "generate_token",
    "validate_token",
    "csrf_protect",
    "before_request",
]
