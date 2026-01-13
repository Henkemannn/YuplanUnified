import pytest


def test_landing_root_anonymous_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Yuplan" in html
    assert "Logga in" in html


def test_landing_root_redirects_superuser(client_superuser):
    r = client_superuser.get("/", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "/ui/admin/dashboard" in loc or "/ui/admin" in loc


def test_landing_root_redirects_admin(client_admin):
    r = client_admin.get("/", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "/ui/admin/dashboard" in loc or "/ui/admin" in loc


def test_landing_root_redirects_kitchen(client_cook):
    r = client_cook.get("/", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/ui/cook/dashboard" in r.headers["Location"]


def test_landing_root_redirects_department(client_user):
    r = client_user.get("/", headers={"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "/portal/week" in loc or "/ui/portal/week" in loc
