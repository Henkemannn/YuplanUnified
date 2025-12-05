import pytest


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_report_ui_readonly_and_headers(client_admin):
    r = client_admin.get("/ui/reports/weekview?site_id=s1&year=2025&week=47", headers=_h("admin"))
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Assert presence of Swedish headers we standardised
    assert "Lunch" in html
    assert "Kväll" in html
    assert "Totalt" in html
    # No forms/write actions under reports
    assert "method=\"post\"" not in html.lower()


def test_weekview_report_endpoint_is_get_only(client_admin):
    # Ensure no POST/PUT/DELETE route exists for UI report path
    app = client_admin.application
    with app.app_context():
        methods = None
        for r in app.url_map.iter_rules():
            if str(r.rule).startswith("/ui/reports/weekview"):
                methods = r.methods
                break
        assert methods is not None
        assert methods == {"GET", "HEAD", "OPTIONS"}
