import uuid
from sqlalchemy import text

HEADERS_PORTAL = {"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}
HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_USER = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _seed_site_dep_week_with_menu():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        year, week = 2025, 2
        # Create site/department
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PortalSite"})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES(:i,:s,:n,'fixed',8,'Faktaruta: Inga risrätter',0)"), {"i": dep_id, "s": site_id, "n": "Avd Portal"})
        # Diet defaults
        db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
        db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,'Gluten',2)"), {"d": dep_id})
        db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,'Laktos',1)"), {"d": dep_id})
        db.commit()
        return site_id, dep_id, year, week
    finally:
        db.close()


def test_portal_week_enhetsportal_view(app_session):
    client = app_session.test_client()
    site_id, dep_id, year, week = _seed_site_dep_week_with_menu()

    # GET portal week as portal role
    r = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Residents and diet defaults summary
    assert "Boendeantal:" in html and "8" in html
    assert "Specialkost på avdelningen" in html
    assert "Gluten" in html and "Laktos" in html
    # Notes
    assert "Faktaruta" in html
    # Ensure data-can-choose-lunch attribute appears on lunch blocks
    assert 'data-can-choose-lunch="' in html
    # Dinner block indicates read-only
    assert "KVÄLLSMAT" in html
    assert "Endast menyvisning" in html
    # Status badge present (complete or not)
    assert ("Veckan är klar" in html) or ("Veckan är inte klar" in html)


def test_portal_week_rbac(app_session):
    client = app_session.test_client()
    site_id, dep_id, year, week = _seed_site_dep_week_with_menu()
    r_bad = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}")
    assert r_bad.status_code in (302, 403, 401)
