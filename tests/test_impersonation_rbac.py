from __future__ import annotations


def test_superuser_cannot_modify_without_impersonation(client_superuser):
    # Acquire token if strict flag enabled
    client_superuser.get("/diet/types", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    with client_superuser.session_transaction() as s:  # type: ignore
        tok = s.get("CSRF_TOKEN")
    headers = {"X-User-Role":"superuser","X-Tenant-Id":"1"}
    if tok:
        headers["X-CSRF-Token"] = tok
    r = client_superuser.post("/diet/types", json={"name": "Glutenfri"}, headers=headers)
    assert r.status_code == 403
    j = r.get_json()
    assert j.get("detail") == "impersonation_required"


def test_superuser_can_modify_with_impersonation(client_superuser):
    client_superuser.get("/diet/types", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    with client_superuser.session_transaction() as s:  # type: ignore
        tok = s.get("CSRF_TOKEN")
    headers = {"X-User-Role":"superuser","X-Tenant-Id":"1"}
    if tok:
        headers["X-CSRF-Token"] = tok
    start = client_superuser.post("/superuser/impersonate/start", json={"tenant_id": 1, "reason": "debug"}, headers=headers)
    assert start.status_code == 200
    if tok:
        headers["X-CSRF-Token"] = tok
    r = client_superuser.post("/diet/types", json={"name": "Laktosfri"}, headers=headers)
    assert r.status_code == 200
    stop = client_superuser.post("/superuser/impersonate/stop", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert stop.status_code == 200


def test_support_ui_superuser_only(client_admin, client_superuser):
    # Admin should now be forbidden
    a = client_admin.get("/admin/support/")
    assert a.status_code in (401,403)
    s = client_superuser.get("/admin/support/", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert s.status_code == 200
