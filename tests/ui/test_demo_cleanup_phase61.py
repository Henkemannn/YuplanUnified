"""
Phase 6.1: Demo & Legacy UI Cleanup
- Demo UI must be disabled by default (/demo -> 404/problem)
- Core unified views should not link to demo assets or routes
"""
from datetime import date


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _current_year_week():
    t = date.today().isocalendar()
    return t[0], t[1]


def test_demo_routes_disabled_by_default(client_admin):
    r = client_admin.get("/demo", headers=_h("admin"))
    assert r.status_code == 404
    # Should serve problem+json envelope for 404s
    assert "application/problem+json" in (r.headers.get("Content-Type") or "")


def test_core_views_have_no_demo_links(client_admin):
    # Cook dashboard
    rc = client_admin.get('/ui/cook', headers=_h('cook'))
    assert rc.status_code == 200
    cook_html = rc.get_data(as_text=True)
    assert '/demo' not in cook_html
    assert 'demo.css' not in cook_html
    assert 'demo.js' not in cook_html

    # Admin dashboard
    ra = client_admin.get('/ui/admin', headers=_h('admin'))
    assert ra.status_code == 200
    admin_html = ra.get_data(as_text=True)
    assert '/demo' not in admin_html
    assert 'demo.css' not in admin_html
    assert 'demo.js' not in admin_html

    # Reports weekly (uses current y/w)
    year, week = _current_year_week()
    rr = client_admin.get(
        f'/ui/reports/weekly?year={year}&week={week}', headers=_h('admin'), follow_redirects=True
    )
    assert rr.status_code == 200
    report_html = rr.get_data(as_text=True)
    assert '/demo' not in report_html
    assert 'demo.css' not in report_html
    assert 'demo.js' not in report_html
