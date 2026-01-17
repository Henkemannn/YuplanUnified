"""Pocket 6 - Central error handling module.

Copilot prompt: Create Flask error registration that returns JSON envelope {'ok': False, 'error', 'message?'} for
400/401/403/404/422/429/500. Provide make_error(error: Literal[…], message: str|None). No Any.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict, cast

from flask import Flask, jsonify
from .http_errors import too_many_requests, unprocessable_entity, bad_request
import os

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
    from .errors import ValidationError, DomainError  # type: ignore

    @app.errorhandler(AuthzError)  # type: ignore[arg-type]
    def _authz(e: AuthzError):  # type: ignore[no-untyped-def]
        # Emit RFC7807 ProblemDetails for forbidden, including required_role when available
        try:
            from flask import jsonify as _jsonify, request
            payload = {
                "type": "https://example.com/errors/forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": str(e) or "forbidden",
                "instance": request.path,
            }
            if e.required:
                payload["required_role"] = e.required  # type: ignore[assignment]
            resp = _jsonify(payload)
            resp.status_code = 403
            resp.mimetype = "application/problem+json"
            return resp
        except Exception:
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
        # Always emit RFC7807 ProblemDetails for 401 Unauthorized
        try:
            from flask import jsonify as _jsonify, g, request
            try:
                from .audit_events import record_audit_event
                record_audit_event(
                    "problem_response", status=401, type="unauthorized", path=request.path
                )
            except Exception:
                pass
            resp = _jsonify({
                "type": "https://example.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": str(e) or "authentication required",
                "instance": request.path,
                "request_id": getattr(g, "request_id", None),
            })
            resp.status_code = 401
            resp.mimetype = "application/problem+json"
            return resp
        except Exception:
            # Fallback envelope if jsonify/context unavailable
            r = make_error("unauthorized", str(e))
            return _attach_code(r, 401)

    @app.errorhandler(RateLimitError)  # type: ignore[arg-type]
    def _rate_limit(e: RateLimitError):  # type: ignore[no-untyped-def]
        # Return RFC7807 ProblemDetails for 429 with optional Retry-After and limit metadata
        retry_after = getattr(e, "retry_after", None)
        limit_name = getattr(e, "limit", None)
        # Use canonical detail "rate_limited" to satisfy tests
        resp = too_many_requests(detail="rate_limited", retry_after=retry_after, limit=limit_name)
        return resp

    # Pagination errors
    from .pagination import PaginationError  # type: ignore

    @app.errorhandler(PaginationError)  # type: ignore[arg-type]
    def _pagination(e: PaginationError):  # type: ignore[no-untyped-def]
        # Return RFC7807 ProblemDetails for 400 Bad Request
        resp = bad_request(detail=str(e) or "bad_request")
        return resp

    # Domain validation errors (RFC7807 422)
    @app.errorhandler(ValidationError)  # type: ignore[arg-type]
    def _validation(e: ValidationError):  # type: ignore[no-untyped-def]
        try:
            resp = unprocessable_entity(getattr(e, "errors", []) or e.extra.get("errors", []), detail=e.detail)
            return resp
        except Exception:
            r = make_error("invalid", str(e))
            return _attach_code(r, 422)

    # Generic DomainError mapping to RFC7807 based on status
    @app.errorhandler(DomainError)  # type: ignore[arg-type]
    def _domain(e: DomainError):  # type: ignore[no-untyped-def]
        try:
            if getattr(e, "status", 400) == 422:
                return unprocessable_entity(getattr(e, "errors", []) or e.extra.get("errors", []), detail=e.detail)
            if getattr(e, "status", 400) == 400:
                return bad_request(detail=e.detail)
            if getattr(e, "status", 400) == 401:
                # Defer to existing 401 handler
                return _attach_code(make_error("unauthorized", e.detail), 401)
            if getattr(e, "status", 400) == 403:
                # Defer to existing 403 handler
                return _attach_code(make_error("forbidden", e.detail), 403)
            # Fallback: envelope with specified status
            return _attach_code(make_error("invalid", e.detail), getattr(e, "status", 400))
        except Exception:
            return _attach_code(make_error("invalid", str(e)), 400)

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
