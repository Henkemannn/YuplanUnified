from __future__ import annotations

import time


def test_impersonation_expiry_auto_clears(client_superuser):
    r = client_superuser.post(
        "/superuser/impersonate/start",
        json={"tenant_id": 1, "reason": "debug"},
        headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"},
    )
    assert r.status_code == 200
    # Force expiry directly in session (no need to call get_impersonation which requires request context)
    with client_superuser.session_transaction() as s:  # type: ignore
        data = s.get("impersonate")
        assert data
        data["expires_at"] = int(time.time()) - 1
        s["impersonate"] = data
    r2 = client_superuser.post(
        "/diet/types",
        json={"name": "Test"},
        headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"},
    )
    assert r2.status_code == 403
    j = r2.get_json()
    assert j.get("status") == 403
    assert j.get("detail") == "impersonation_required"
    assert j.get("type") == "https://example.com/problems/impersonation-required"


def test_impersonation_required_problem_shape(client_superuser):
    r = client_superuser.post(
        "/diet/types", json={"name": "Gf"}, headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    )
    assert r.status_code == 403
    j = r.get_json()
    assert j.get("type") == "https://example.com/problems/impersonation-required"
    assert j.get("detail") == "impersonation_required"
    assert j.get("title") == "Forbidden"
