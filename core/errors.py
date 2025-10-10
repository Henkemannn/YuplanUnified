"""Domain error system + RFC7807 handler registration.

Keeps legacy APIError classes (minimal) for backward compatibility while
introducing DomainError / ValidationError for problem+json mode.
"""
from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from typing import Any

from flask import request
from werkzeug.wrappers.response import Response

from .app_authz import AuthzError
from .app_sessions import SessionError
from .audit_events import record_audit_event
from .http_errors import (
    bad_request,
    conflict,
    forbidden,
    internal_server_error,
    not_found,
    too_many_requests,
    unauthorized,
    unprocessable_entity,
)
from .pagination import PaginationError
from .rate_limiter import RateLimitError


# ---- Legacy APIError (retained) ----
class APIError(Exception):
    status_code = 400
    error_code = "bad_request"
    def __init__(self, message: str | None = None, *, error: str | None = None, status: int | None = None):
        super().__init__(message or self.error_code)
        if error:
            self.error_code = error
        if status:
            self.status_code = status
        self.message = message or self.error_code

class LegacyValidationError(APIError):  # renamed to avoid clash
    status_code = 400
    error_code = "validation_error"

# ---- New Domain Errors ----
class DomainError(Exception):
    def __init__(self, status: int, code: str, detail: str | None = None, **extra: Any):
        self.status = status
        self.code = code
        self.detail = detail or code
        self.extra = extra
        super().__init__(self.detail)

class ValidationError(DomainError):
    def __init__(self, errors: Any, detail: str = "validation_error", **extra: Any):
        super().__init__(422, "validation_error", detail, errors=errors, **extra)
        self.errors = errors

# ---- Legacy shim exceptions expected by older blueprints/tests ----
class NotFoundError(APIError):  # pragma: no cover (thin shim)
    status_code = 404
    error_code = "not_found"

# Preserve original ValidationError import path expectation
LegacyValidationErrorAlias = LegacyValidationError

_STATUS_HELPERS: dict[int, Callable[..., Response]] = {
    400: bad_request,
    401: unauthorized,
    403: forbidden,
    404: not_found,
    409: conflict,
    422: unprocessable_entity,
    429: too_many_requests,
}

def _emit_problem(resp_payload: dict[str, Any]) -> None:
    try:
        record_audit_event(
            "problem_response",
            actor_user_id=None,
            tenant_id=None,
            type=resp_payload.get("type"),
            status=resp_payload.get("status"),
            detail=resp_payload.get("detail"),
            path=request.path,
        )
    except Exception:
        pass

def register_error_handlers(app: Any) -> None:  # pragma: no cover - integration path
    from werkzeug.exceptions import HTTPException
    # Unconditional RFC7807 adoption (ADR-003)

    @app.errorhandler(SessionError)
    def _h_session(err: SessionError) -> Response:
        resp = unauthorized(detail=str(err) or "authentication_required")
        _emit_problem(resp.get_json())
        return resp

    @app.errorhandler(AuthzError)
    def _h_authz(err: AuthzError) -> Response:
        # Include required role when available
        required = getattr(err, "required", None)
        extra = {"required_role": required} if required else {}
        resp = forbidden(detail=str(err) or "forbidden", **extra)
        _emit_problem(resp.get_json())
        return resp

    @app.errorhandler(DomainError)
    def _h_domain(err: DomainError) -> Response:
        helper = _STATUS_HELPERS.get(err.status)
        if err.status == 422:
            resp = unprocessable_entity(err.extra.get("errors") or getattr(err, "errors", []), detail=err.detail, **{k:v for k,v in err.extra.items() if k != "errors"})
        elif helper:
            resp = helper(detail=err.detail, **err.extra)
        else:
            resp = bad_request(detail=err.detail, **err.extra)
        _emit_problem(resp.get_json())
        return resp

    @app.errorhandler(HTTPException)
    def _h_http(ex: HTTPException) -> Response:
        status = ex.code or 500
        helper = _STATUS_HELPERS.get(status)
        if helper:
            resp = helper(detail=ex.description)
        elif status >= 500:
            resp = internal_server_error()
        else:
            resp = bad_request(detail=str(ex.description))
        _emit_problem(resp.get_json())
        return resp

    @app.errorhandler(RateLimitError)  # type: ignore[arg-type]
    def _h_rate_limit(ex: RateLimitError) -> Response:
        # Map to 429 with retry_after
        retry_after = getattr(ex, "retry_after", None)
        limit = getattr(ex, "limit", None)
        resp = too_many_requests(detail="rate_limited", retry_after=retry_after, limit=limit)
        payload = resp.get_json()
        try:
            record_audit_event("problem_response", status=429, type=payload.get("type"), path=request.path)
        except Exception:
            pass
        return resp

    @app.errorhandler(PaginationError)
    def _h_pagination(err: PaginationError) -> Response:
        # Normalize pagination errors to 400 Bad Request with detail
        resp = bad_request(detail=str(err) or "bad_request")
        _emit_problem(resp.get_json())
        return resp

    @app.errorhandler(Exception)
    def _h_exception(ex: Exception) -> Response:
        incident_id = str(uuid.uuid4())
        app.logger.error("Unhandled exception incident_id=%s path=%s\n%s", incident_id, request.path, traceback.format_exc())
        resp = internal_server_error(incident_id=incident_id)
        payload = resp.get_json()
        try:
            record_audit_event("incident", actor_user_id=None, tenant_id=None, incident_id=incident_id, path=request.path)
            _emit_problem(payload)
        except Exception:
            pass
        return resp

__all__ = [
    "APIError","DomainError","ValidationError","LegacyValidationError","NotFoundError","LegacyValidationErrorAlias","register_error_handlers"
]
