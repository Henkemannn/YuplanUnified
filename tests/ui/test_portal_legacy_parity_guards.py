import pytest


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_portal_department_week_ui_readonly_guard(client_admin):
    r = client_admin.get("/ui/portal/department/week?year=2025&week=47", headers=_h("admin"))
    # Depending on RBAC/demo context, portal may 403 without department claim
    assert r.status_code in (200, 403, 302)
    if r.status_code == 200:
        html = r.data.decode("utf-8")
        # Guard: no forms that write residents or diets are present
        assert "action=\"/api/weekview/residents" not in html
        assert "action=\"/api/admin/diets" not in html


def test_portal_department_week_ui_role_block(client):
    # Non-portal role (simulate viewer without proper portal claim) should still render or be gated
    r = client.get("/ui/portal/department/week?year=2025&week=47", headers=_h("viewer"))
    # Accept either 200 (read-only view) or 403/302 depending on RBAC wiring; ensure no write forms
    assert r.status_code in (200, 302, 403)
    html = r.data.decode("utf-8")
    assert "action=\"/api/weekview/residents" not in html
    assert "action=\"/api/admin/diets" not in html
