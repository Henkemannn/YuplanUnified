"""Shared RFC7807 problem+json helpers for consistent error responses."""
from __future__ import annotations

import uuid

from flask import g, jsonify
from werkzeug.wrappers.response import Response


def problem(status: int, type_: str, title: str, detail: str, **extra: object) -> Response:
    payload = {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
    }
    rid = getattr(g, "request_id", None)
    if rid:
        payload["request_id"] = rid
    for k, v in extra.items():
        if v is not None:
            payload[k] = v
    resp = jsonify(payload)
    resp.status_code = status
    resp.mimetype = "application/problem+json"
    # Always echo request id header when available
    if rid and "X-Request-Id" not in resp.headers:
        resp.headers["X-Request-Id"] = rid
    return resp


def forbidden(detail: str, problem_type: str = "https://example.com/problems/forbidden", **extra: object) -> Response:
    return problem(403, problem_type, "Forbidden", detail, **extra)


def csrf_missing() -> Response:
    return forbidden("csrf_missing", problem_type="https://example.com/problems/csrf_missing")


def csrf_invalid() -> Response:
    return forbidden("csrf_invalid", problem_type="https://example.com/problems/csrf_invalid")

# Canonical builders (RFC7807 sweep)
_BASE_TYPE_PREFIX = "https://example.com/errors/"

def _ptype(slug: str) -> str:
    return _BASE_TYPE_PREFIX + slug

def _std(status: int, slug: str, title: str, detail: str | None = None, **extra: object) -> Response:
    d = detail if detail is not None else slug
    return problem(status, _ptype(slug), title, d, **extra)

def bad_request(detail: str = "bad_request", **extra: object) -> Response:
    return _std(400, "bad_request", "Bad Request", detail, **extra)

def unauthorized(detail: str = "unauthorized", www_auth: str | None = None, **extra: object) -> Response:
    resp = _std(401, "unauthorized", "Unauthorized", detail, **extra)
    if www_auth:
        resp.headers["WWW-Authenticate"] = www_auth
    return resp

def conflict(detail: str = "conflict", **extra: object) -> Response:
    return _std(409, "conflict", "Conflict", detail, **extra)

def not_found(detail: str = "not_found", **extra: object) -> Response:
    return _std(404, "not_found", "Not Found", detail, **extra)

def unprocessable_entity(errors: object | list[dict[str, object]], detail: str = "validation_error", **extra: object) -> Response:
    return _std(422, "validation_error", "Unprocessable Entity", detail, errors=errors, **extra)

def too_many_requests(detail: str = "rate_limited", retry_after: int | None = None, **extra: object) -> Response:
    # Allow arbitrary metadata like limit name; surface retry_after in both header and body
    resp = _std(429, "rate_limited", "Too Many Requests", detail, retry_after=retry_after, **extra)
    if retry_after is not None:
        try:
            resp.headers["Retry-After"] = str(int(retry_after))
        except Exception:
            pass
    return resp

def internal_server_error(detail: str = "internal_error", incident_id: str | None = None, **extra: object) -> Response:
    if not incident_id:
        incident_id = str(uuid.uuid4())
    return _std(500, "internal_error", "Internal Server Error", detail, incident_id=incident_id, **extra)

__all__ = [
    "problem","forbidden","csrf_missing","csrf_invalid","bad_request","unauthorized","conflict","not_found","unprocessable_entity","too_many_requests","internal_server_error"
]
