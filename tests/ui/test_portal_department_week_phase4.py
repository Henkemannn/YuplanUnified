import pytest

def test_portal_week_shows_department_info(client_admin):
    r = client_admin.get("/portal/week?site_id=s1&department_id=d1&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Boende:" in html


def test_portal_week_shows_status_label(client_admin):
    r = client_admin.get("/portal/week?site_id=s1&department_id=d1&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert ("Klar" in html) or ("Behöver val" in html) or ("Ingen meny" in html)


def test_portal_week_has_back_link(client_admin):
    r = client_admin.get("/portal/week?site_id=s1&department_id=d1&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "&larr; Till vecköversikten" in html


def test_portal_week_shows_alt_options(client_admin):
    r = client_admin.get("/portal/week?site_id=s1&department_id=d1&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "ALT 1" in html or "Alt1" in html
    assert "ALT 2" in html or "Alt2" in html
