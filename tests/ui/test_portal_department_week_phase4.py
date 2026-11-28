import pytest

from tests._auth_site_helpers import login_bound_user


@pytest.fixture(autouse=True)
def bound_portal_site(client_admin):
    from sqlalchemy import text
    from core.db import get_session

    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO sites(id, tenant_id, name) VALUES ('phase4-site', 1, 'Phase 4 site')"))
        db.execute(text(
            "INSERT OR IGNORE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
            "VALUES ('phase4-department', 'phase4-site', 'Phase 4 department', 'fixed', 5)"
        ))
        db.commit()
    finally:
        db.close()
    login_bound_user(client_admin, site_id="phase4-site")


def test_portal_week_shows_department_info(client_admin):
    r = client_admin.get("/portal/week?site_id=phase4-site&department_id=phase4-department&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Boende:" in html


def test_portal_week_shows_status_label(client_admin):
    r = client_admin.get("/portal/week?site_id=phase4-site&department_id=phase4-department&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert ("Klar" in html) or ("Behöver val" in html) or ("Ingen meny" in html)


def test_portal_week_has_back_link(client_admin):
    r = client_admin.get("/portal/week?site_id=phase4-site&department_id=phase4-department&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "&larr; Till vecköversikten" in html


def test_portal_week_shows_alt_options(client_admin):
    r = client_admin.get("/portal/week?site_id=phase4-site&department_id=phase4-department&year=2025&week=47", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "ALT 1" in html or "Alt1" in html
    assert "ALT 2" in html or "Alt2" in html
