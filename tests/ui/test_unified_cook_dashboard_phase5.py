import pytest


def test_cook_dashboard_requires_kitchen_or_admin(client_admin, client_superuser, client_cook, client_no_tenant):
    # Admin
    r = client_admin.get("/ui/cook/dashboard", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    # Superuser
    r = client_superuser.get("/ui/cook/dashboard", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    # Cook
    r = client_cook.get("/ui/cook/dashboard", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    # Viewer/department (no tenant)
    r = client_no_tenant.get("/ui/cook/dashboard", headers={"X-User-Role": "viewer"})
    assert r.status_code in (401, 403)


def test_cook_dashboard_shows_totals_and_sites(client_admin):
    r = client_admin.get("/ui/cook/dashboard", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Kockvy" in html
    # Totals panel keywords
    assert "Dagens totals" in html or "Totals" in html
    assert "Normalkost" in html
    assert "Special" in html
    # At least one actions link placeholder
    assert "/ui/planera/day" in html
    assert "/ui/weekview" in html or "/ui/portal/week" in html
    assert "/ui/reports/weekly" in html or "/ui/reports/weekly.xlsx" in html


def test_cook_dashboard_respects_date_param(client_admin):
    r = client_admin.get("/ui/cook/dashboard?date=2025-12-06", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "2025-12-06" in html
