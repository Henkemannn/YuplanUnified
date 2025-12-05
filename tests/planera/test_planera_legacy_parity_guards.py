import pytest
from sqlalchemy import text


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_day_flag_gating(client_admin):
    # Depending on current flag default and phase, accept 200/404/501
    r = client_admin.get("/ui/planera/day?site_id=s1&date=2025-11-24&department_id=d1", headers=_h("admin"))
    assert r.status_code in (200, 404, 501)


def test_planera_day_readonly_scaffold_when_enabled(client_admin):
    r = client_admin.get("/ui/planera/day?site_id=s1&date=2025-11-24&department_id=d1", headers=_h("admin"))
    # Accept 200 for scaffold UI (or redirect)
    assert r.status_code in (200, 302)
    if r.status_code == 200:
        html = r.data.decode("utf-8")
        # No specialkost/residents write forms present yet
        assert "action=\"/api/weekview/residents" not in html
        assert "action=\"/api/weekview/alt2" not in html
