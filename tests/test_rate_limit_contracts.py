from __future__ import annotations

from flask import Flask


def test_legacy_rate_limit_has_retry_after_header_and_json_fields(client_admin: Flask):
    # Deterministic legacy 429 endpoint
    r = client_admin.get("/_test/limit_legacy")
    assert r.status_code == 429
    assert r.headers.get("Retry-After") is not None
    data = r.get_json()
    assert data["error"] == "rate_limited"
    assert isinstance(data.get("retry_after"), int)
    assert isinstance(data.get("limit"), str)


def test_pilot_rate_limit_problemjson_has_retry_after(client: Flask):
    # Deterministic pilot 429 endpoint (diet path is pilot)
    r = client.get("/diet/_test/limit_pilot")
    assert r.status_code == 429
    assert r.headers.get("Content-Type", "").startswith("application/problem+json")
    data = r.get_json()
    assert data["status"] == 429
    assert data["detail"] == "rate_limited"
    assert isinstance(data.get("retry_after"), int)
