import uuid
from sqlalchemy import text

HEADERS_SUPERUSER = {"X-User-Role": "superuser", "X-Tenant-Id": "1"}
HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_USER = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteNav"})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES(:i,:s,:n,'fixed',5,'',0)"), {"i": dep_id, "s": site_id, "n": "Avd Nav"})
        # Ensure diet defaults table exists to render settings page
        db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
        db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,'Gluten',1)"), {"d": dep_id})
        db.commit()
        return site_id, dep_id
    finally:
        db.close()


def test_systemadmin_shows_settings_link(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_and_department()

    # View systemadmin page as superuser
    r_sys = client.get(f"/ui/admin/system?site_id={site_id}", headers=HEADERS_SUPERUSER)
    assert r_sys.status_code == 200
    html = r_sys.get_data(as_text=True)
    assert "Systemadministration" in html
    assert "Avd Nav" in html
    # The settings link should be present
    assert f"/ui/admin/departments/{dep_id}/settings" in html

    # Follow settings link as admin
    r_settings = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN)
    assert r_settings.status_code == 200
    shtml = r_settings.get_data(as_text=True)
    assert "Avdelningsinställningar" in shtml
    assert "Boendeantal" in shtml
    assert "Specialkost" in shtml or "Specialkost på avdelningen" in shtml
    assert "Faktaruta" in shtml or "Faktaruta / särskild info" in shtml


def test_settings_rbac_denied_for_non_admin(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_and_department()

    r_settings = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_USER)
    assert r_settings.status_code in (302, 403, 401)
