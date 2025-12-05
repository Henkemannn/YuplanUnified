import uuid
from sqlalchemy import text

HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_COOK = {"X-User-Role": "cook", "X-Tenant-Id": "1"}


def _seed_site_dep_defaults(site_name="TestSite"):
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": site_name})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES(:i,:s,:n,'fixed',8,'Initial note',0)"), {"i": dep_id, "s": site_id, "n": "Avd X"})
        # Diet defaults table
        db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
        db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,'Gluten',2)"), {"d": dep_id})
        db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,'Laktos',1)"), {"d": dep_id})
        db.commit()
        return site_id, dep_id
    finally:
        db.close()


def test_admin_settings_get_and_post(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep_defaults()

    # GET as admin
    r_get = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN)
    assert r_get.status_code == 200
    html = r_get.get_data(as_text=True)
    assert "Avdelningsinställningar" in html
    assert "Avd X" in html
    assert "Antal boende totalt" in html
    assert "Initial note" in html
    assert "Gluten" in html and "Laktos" in html

    # POST updates: residents 10, Gluten 3, note changed
    form = {
        "residents_base_count": "10",
        "notes": "Uppdaterad faktaruta",
        "diet_type_id[]": ["Gluten", "Laktos"],
        "planned_count[]": ["3", "1"],
    }
    r_post = client.post(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN, data=form)
    # Depending on test client settings, POST may return 302 redirect or already-followed 200
    assert r_post.status_code in (200, 302, 303)
    r_get2 = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN)
    assert r_get2.status_code == 200
    html2 = r_get2.get_data(as_text=True)
    assert "value=\"10\"" in html2
    assert "Uppdaterad faktaruta" in html2
    # Updated planned_count should reflect 3 for Gluten
    assert "Gluten" in html2 and "value=\"3\"" in html2

    # RBAC: cook should be allowed (SAFE_UI_ROLES), but a role outside should be blocked
    # Use a non-admin role to verify access denied
    r_forbidden = client.get(f"/ui/admin/departments/{dep_id}/settings", headers={"X-User-Role": "user", "X-Tenant-Id": "1"})
    assert r_forbidden.status_code in (302, 403, 401)


def test_admin_settings_integration_with_weekview_report(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep_defaults()

    # After changing defaults, weekview report should reflect planned counts via debiterbar logic when marked.
    # Simple check: CSV header present and contains department name; we won't mark here.
    year, week = 2025, 12
    # ensure site context
    resp_csv = client.get(f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}", headers=HEADERS_ADMIN)
    assert resp_csv.status_code == 200
    body = resp_csv.data.decode("utf-8")
    assert "site,department,year,week,meal,residents_total,debiterbar_specialkost,normal_count" in body.splitlines()[0]
    # Department name appears somewhere in rows
    assert any("Avd X" in ln for ln in body.splitlines()[1:])
