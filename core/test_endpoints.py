from __future__ import annotations

from flask import Blueprint, jsonify, make_response

bp = Blueprint("test_endpoints", __name__)


@bp.get("/_test/limit_legacy")
def test_limit_legacy():
    resp = make_response(
        jsonify({
            "ok": False,
            "error": "rate_limited",
            "message": "Too many requests",
            "retry_after": 1,
            "limit": "legacy",
        }),
        429,
    )
    resp.headers["Retry-After"] = "1"
    resp.headers.setdefault("Content-Type", "application/json")
    return resp

@bp.get("/diet/_test/limit_pilot")
def test_limit_pilot():
    payload = {
        "type": "about:blank",
        "title": "Too Many Requests",
        "status": 429,
        "detail": "rate_limited",
        "retry_after": 1,
    }
    resp = make_response(jsonify(payload), 429)
    resp.headers["Retry-After"] = "1"
    resp.headers["Content-Type"] = "application/problem+json"
    return resp

@bp.get("/_test/boom")
def test_boom():
    # Simulate an incident to exercise 500 ProblemDetails
    raise RuntimeError("simulated incident")
