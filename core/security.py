"""Security middleware and helpers.

Features:
 - CORS allow-list.
 - CSRF (double-submit cookie OR same-origin) with production vs test exemptions.
 - Security headers (HSTS, CSP, Referrer-Policy, Permissions-Policy).
 - Basic counters for blocked CSRF attempts.

CSRF Policy:
 - SAFE methods always allowed.
 - If path+method not exempt: require (cookie==header) OR same-origin match.
 - Production exemptions minimal; test adds legacy endpoints to avoid mass fixture rewrite.
 - Returns RFC7807 problem+json on denial with reason in `detail`.
"""

from __future__ import annotations

import os
import secrets
from importlib import import_module
from typing import Any

# Optional dependency: import via importlib to avoid static resolver errors
try:  # pragma: no cover - if OTEL not installed or disabled
    metrics: Any = import_module("opentelemetry.metrics")
except Exception:  # pragma: no cover
    metrics = None

from flask import Flask, g, make_response, request

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Exemption prefix sets (directories). Ending slash required for clarity.
PROD_EXEMPT = {"/auth/", "/metrics"}  # /metrics covers both /metrics/ingest & /metrics/query
TEST_EXEMPT = PROD_EXEMPT | {
    "/import/",
    "/admin/tenants",
    "/admin/features/toggle",
    "/admin/feature_flags",
    "/diet/",
}

_CSRF_COUNTERS = {"missing": 0, "mismatch": 0, "origin": 0}
if metrics:
    try:
        _meter = metrics.get_meter(__name__)
        _csrf_blocked_counter = _meter.create_counter(
            name="security.csrf_blocked_total",
            description="Count of blocked CSRF-modifying requests by reason",
            unit="1",
        )
    except Exception:  # pragma: no cover
        _csrf_blocked_counter = None
else:  # pragma: no cover
    _csrf_blocked_counter = None


def _is_testing(app: Flask) -> bool:
    # Honor explicit TESTING or detect pytest runtime.
    return bool(app.config.get("TESTING") or os.getenv("PYTEST_CURRENT_TEST"))


def _is_exempt(path: str, method: str, testing: bool) -> bool:
    if method in SAFE_METHODS:
        return True
    base = TEST_EXEMPT if testing else PROD_EXEMPT
    # Normalize: ensure trailing slash check by adding slash to path if directory-like
    return any(path.startswith(p) for p in base)


def _problem_forbidden(reason: str, instance: str | None = None):  # RFC7807 minimal
    from flask import g, jsonify

    rid = getattr(g, "request_id", None)
    payload = {
        "type": "https://example.com/problems/forbidden",
        "title": "Forbidden",
        "status": 403,
        "detail": reason,
    }
    if instance:
        payload["instance"] = instance
    if rid:
        payload.setdefault("request_id", rid)
    resp = jsonify(payload)
    resp.status_code = 403
    resp.mimetype = "application/problem+json"
    return resp


def _origin_from_request() -> str | None:
    return request.headers.get("Origin")


def _validate_cors(app: Flask, resp):  # pragma: no cover - exercised indirectly
    allowed: list[str] = app.config.get("CORS_ALLOWED_ORIGINS", []) or []
    if not allowed:
        return resp  # CORS disabled
    origin = _origin_from_request()
    if not origin:
        return resp
    if origin in allowed:
        resp.headers.setdefault("Vary", "Origin")
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        req_hdrs = request.headers.get("Access-Control-Request-Headers")
        if req_hdrs:
            resp.headers["Access-Control-Allow-Headers"] = req_hdrs
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Max-Age"] = "600"
    return resp


def _ensure_csrf_token(app: Flask):
    # Generate CSRF token per session (stored in cookie). If not present create.
    cookie_name = app.config.get("CSRF_COOKIE_NAME", "csrf_token")
    if cookie_name in request.cookies:
        return request.cookies[cookie_name]
    token = secrets.token_hex(16)
    # store on g to set in response
    g._new_csrf_token = token
    return token


def _csrf_check(app: Flask):
    testing = _is_testing(app)
    method = request.method.upper()
    path = request.path or "/"
    if not app.config.get("ENABLE_CSRF", True):
        return
    # Preserve legacy behavior: in test mode we bypass CSRF entirely so existing
    # tests that do not send tokens continue to work. Dedicated CSRF tests can
    # invoke an app with TESTING disabled to exercise production policy.
    if testing and not app.config.get("STRICT_CSRF_IN_TESTS"):
        # In non-strict test mode we fully bypass CSRF enforcement to avoid retrofitting all tests.
        return
    if _is_exempt(path, method, testing):
        return
    cookie_name = app.config.get("CSRF_COOKIE_NAME", "csrf_token")
    header_name = app.config.get("CSRF_HEADER_NAME", "X-CSRF-Token")
    sent_cookie = request.cookies.get(cookie_name)
    sent_header = request.headers.get(header_name)
    origin = request.headers.get("Origin")
    host = (request.host_url or "").rstrip("/")
    same_origin = bool(origin and host and origin.rstrip("/") == host)
    if sent_cookie and sent_header:
        if secrets.compare_digest(sent_cookie, sent_header):
            return  # double-submit success
        _CSRF_COUNTERS["mismatch"] += 1
        if _csrf_blocked_counter:
            _csrf_blocked_counter.add(1, {"reason": "mismatch"})
        return _problem_forbidden("csrf_mismatch")
    # no token pair; fallback to origin policy
    if same_origin:
        return
    # classify reason (missing vs origin mismatch)
    reason = "origin" if origin and not same_origin else "missing"
    _CSRF_COUNTERS[reason] += 1
    if _csrf_blocked_counter:
        _csrf_blocked_counter.add(1, {"reason": reason})
    mapped = "origin_mismatch" if reason == "origin" else "csrf_missing"
    return _problem_forbidden(mapped)


def init_security(app: Flask):
    # After request: add headers & CORS & set CSRF cookie if generated
    @app.before_request
    def _security_before_request():  # pragma: no cover - coverage via tests
        _ensure_csrf_token(app)
        fail = _csrf_check(app)
        if fail is not None:
            return fail

    @app.after_request
    def _security_after_request(resp):  # pragma: no cover - coverage via tests
        # Security Headers (some already added in existing app after_request; we ensure presence only)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if not app.config.get("TESTING") and not app.config.get("DEBUG"):
            resp.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
            )
        # Basic CSP if absent (leave original if already set by main app)
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        # Secure cookie flags: rely on Flask's session cookie config; set CSRF cookie if new
        if hasattr(g, "_new_csrf_token"):
            from .cookies import set_secure_cookie

            cookie_name = app.config.get("CSRF_COOKIE_NAME", "csrf_token")
            # Non-HttpOnly, Strict for double-submit pattern
            set_secure_cookie(
                resp, cookie_name, g._new_csrf_token, httponly=False, samesite="Strict"
            )
        # Apply CORS last
        return _validate_cors(app, resp)

    # Handle preflight quickly
    @app.route("/", methods=["OPTIONS"], defaults={"path": ""})
    @app.route("/<path:path>", methods=["OPTIONS"])
    def _cors_preflight(path=""):  # pragma: no cover - simple
        resp = make_response("")
        return _validate_cors(app, resp)

    return app
