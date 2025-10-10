from __future__ import annotations

import pytest

# These tests assume env flag enabled; we simulate by overriding app config during test.

@pytest.fixture(scope="module")
def strict_app(app_session):
    app_session.config.update({"YUPLAN_STRICT_CSRF": True})
    return app_session

@pytest.fixture(autouse=True, scope="module")
def _reset_flag_after_module(strict_app):
    yield
    strict_app.config.update({"YUPLAN_STRICT_CSRF": False})

@pytest.fixture
def strict_client(strict_app):
    return strict_app.test_client()


def _get_token(client):
    # Trigger a GET on a path under enforced prefix to set token
    client.get("/diet/types", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    with client.session_transaction() as s:  # type: ignore
        return s.get("CSRF_TOKEN")


def test_csrf_missing_header_returns_403_problemjson(strict_client):
    r = strict_client.post("/diet/types", json={"name": "A"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 403
    j = r.get_json()
    assert j.get("detail") == "csrf_missing"
    assert j.get("type") == "https://example.com/problems/csrf_missing"


def test_csrf_invalid_token_returns_403_problemjson(strict_client):
    # Provide wrong token
    r = strict_client.post("/diet/types", json={"name": "B"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1","X-CSRF-Token":"bad"})
    assert r.status_code == 403
    j = r.get_json()
    assert j.get("detail") == "csrf_invalid"


def test_csrf_valid_token_allows_post(strict_client):
    tok = _get_token(strict_client)
    r = strict_client.post("/diet/types", json={"name": "C"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1","X-CSRF-Token":tok})
    assert r.status_code in (200,400)  # 400 possible if service rejects name; success path 200


def test_csrf_feature_flag_off_no_enforcement(client_admin):
    # Ensure flag disabled
    client_admin.application.config.update({"YUPLAN_STRICT_CSRF": False})
    # Base client has flag off; no token required
    r = client_admin.post("/diet/types", json={"name": "D"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    # Should not be 403 due to CSRF
    assert r.status_code != 403


def test_csrf_exempt_endpoints_unaffected(strict_client):
    # Not currently enforced by strict CSRF rollout; should succeed or return other domain errors but not csrf_missing
    r = strict_client.post("/superuser/impersonate/start", json={"tenant_id":1,"reason":"dbg"}, headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert r.status_code != 403 or r.get_json().get("detail") != "csrf_missing"
