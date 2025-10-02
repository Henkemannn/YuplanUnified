"""Pocket 6 - Central error handling module.

Copilot prompt: Create Flask error registration that returns JSON envelope {'ok': False, 'error', 'message?'} for
400/401/403/404/422/429/500. Provide make_error(error: Literal[…], message: str|None). No Any.
"""
from __future__ import annotations

from typing import Literal, NotRequired, TypedDict, cast

from flask import Flask, jsonify

ErrorCode = Literal[
    "not_found",
    "forbidden",
    "unauthorized",
    "invalid",
    "rate_limited",
    "conflict",
    "unsupported",
    "internal",
]

class ErrorResponse(TypedDict):
    ok: Literal[False]
    error: ErrorCode
    message: NotRequired[str]


def make_error(error: ErrorCode, message: str | None = None):  # -> Response
    payload: ErrorResponse = {"ok": False, "error": error}
    if message:
        payload["message"] = message
    resp = jsonify(payload)
    return resp

_STATUS_MAPPING: dict[int, ErrorCode] = {
    400: "invalid",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "invalid",
    429: "rate_limited",
    409: "conflict",
    415: "unsupported",
}


def _attach_code(resp, status: int):
    # mutate status and return
    resp.status_code = status
    return resp


def register_error_handlers(app: Flask) -> None:
    # Specific domain exceptions (import lazily to avoid circulars)
    from .app_authz import AuthzError  # type: ignore
    from .app_sessions import SessionError  # type: ignore
    from .rate_limiter import RateLimitError  # type: ignore

    @app.errorhandler(AuthzError)  # type: ignore[arg-type]
    def _authz(e: AuthzError):  # type: ignore[no-untyped-def]
        r = make_error("forbidden", str(e))
        if e.required:
            try:
                data = r.get_json() or {}
                if isinstance(data, dict):
                    data.setdefault("required_role", e.required)
                    from flask import jsonify as _json
                    r = _json(data)
            except Exception:
                pass
        return _attach_code(r, 403)

    @app.errorhandler(SessionError)  # type: ignore[arg-type]
    def _session(e: SessionError):  # type: ignore[no-untyped-def]
        r = make_error("unauthorized", str(e))
        return _attach_code(r, 401)
    
    @app.errorhandler(RateLimitError)  # type: ignore[arg-type]
    def _rate_limit(e: RateLimitError):  # type: ignore[no-untyped-def]
        r = make_error("rate_limited", str(e) or "Too many requests")
        try:
            data = r.get_json() or {}
            if isinstance(data, dict):
                data.setdefault("retry_after", getattr(e, "retry_after", None))
                if getattr(e, "limit", None):
                    data.setdefault("limit", e.limit)
                from flask import jsonify as _json
                r = _json(data)
        except Exception:
            pass
        r.headers["Retry-After"] = str(getattr(e, "retry_after", 1))
        return _attach_code(r, 429)
    # Pagination errors
    from .pagination import PaginationError  # type: ignore

    @app.errorhandler(PaginationError)  # type: ignore[arg-type]
    def _pagination(e: PaginationError):  # type: ignore[no-untyped-def]
        r = make_error("invalid", str(e))
        return _attach_code(r, 400)
    # Generic handlers mapping status codes to unified envelope.
    for status, code in _STATUS_MAPPING.items():
        def _handler(e, _status: int = status, _code: ErrorCode = code):  # type: ignore[no-untyped-def]
            msg = getattr(e, "description", None) or getattr(e, "message", None) or None
            r = make_error(_code, cast(str | None, msg))
            return _attach_code(r, _status)
        app.register_error_handler(status, _handler)  # type: ignore[arg-type]

    # Fallback 500
    @app.errorhandler(500)  # type: ignore[arg-type]
    def _internal(e):  # type: ignore[no-untyped-def]
        r = make_error("internal")
        return _attach_code(r, 500)

__all__ = [
    "ErrorCode",
    "ErrorResponse",
    "make_error",
    "register_error_handlers",
]
