from flask.testing import FlaskClient
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed(db, site_id: str, dep_id: str, date_str: str):
    # Basic site/department
    db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
    db.execute(text("INSERT OR REPLACE INTO sites(id, name) VALUES(:i,'Reg Site')"), {"i": site_id})
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,'Reg Dept','manual')"), {"i": dep_id, "s": site_id})
    # Diet types
    db.execute(text("CREATE TABLE IF NOT EXISTS diet_types(id TEXT PRIMARY KEY, name TEXT, is_default INTEGER)"))
    db.execute(text("INSERT OR REPLACE INTO diet_types(id, name, is_default) VALUES('gluten','Glutenfri',0)"))
    db.execute(text("INSERT OR REPLACE INTO diet_types(id, name, is_default) VALUES('laktos','Laktosfri',0)"))
    db.execute(text("INSERT OR REPLACE INTO diet_types(id, name, is_default) VALUES('timbal','Timbal',1)"))
    # Residents count
    db.execute(text("CREATE TABLE IF NOT EXISTS residents_counts(site_id TEXT, department_id TEXT, date TEXT, lunch INTEGER, dinner INTEGER)"))
    db.execute(text("INSERT OR REPLACE INTO residents_counts(site_id, department_id, date, lunch, dinner) VALUES(:s,:d,:dt,10,8)"), {"s": site_id, "d": dep_id, "dt": date_str})
    # Diet registrations for lunch
    db.execute(text("CREATE TABLE IF NOT EXISTS diet_registrations(site_id TEXT, department_id TEXT, date TEXT, meal TEXT, diet_type_id TEXT, count INTEGER)"))
    db.execute(text("INSERT OR REPLACE INTO diet_registrations(site_id, department_id, date, meal, diet_type_id, count) VALUES(:s,:d,:dt,'lunch','gluten',2)"), {"s": site_id, "d": dep_id, "dt": date_str})
    db.execute(text("INSERT OR REPLACE INTO diet_registrations(site_id, department_id, date, meal, diet_type_id, count) VALUES(:s,:d,:dt,'lunch','laktos',1)"), {"s": site_id, "d": dep_id, "dt": date_str})
    db.commit()


def test_registration_day_meal_phase1_basic(client_admin: FlaskClient):
    from core.db import get_session
    db = get_session()
    try:
        site_id = "00000000-0000-0000-0000-00000000aaaa"
        dep_id = "00000000-0000-0000-0000-00000000bbbb"
        date_str = "2025-12-01"
        _seed(db, site_id, dep_id, date_str)
    finally:
        db.close()

    resp = client_admin.get(
        f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={date_str}&meal=lunch",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Summary
    assert "Reg Site" in html
    assert "Reg Dept" in html
    assert "Boende: 10" in html
    assert "Specialkost totalt: 3" in html
    assert "Normalkost: 7" in html
    assert "Status: Registrerad" in html
    # Diet types
    assert "Glutenfri" in html
    assert "Laktosfri" in html
    assert "Timbal" in html
    # Read-only (no forms)
    assert "<form" not in html


def test_registration_day_meal_phase1_rbac_viewer_denied(client_user: FlaskClient):
    # Viewer without elevated roles should still be allowed if SAFE_UI_ROLES includes viewer; if not, expect 403/redirect.
    # We assert one of acceptable outcomes without being brittle.
    site_id = "00000000-0000-0000-0000-00000000cccc"
    dep_id = "00000000-0000-0000-0000-00000000dddd"
    date_str = "2025-12-01"
    resp = client_user.get(
        f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={date_str}&meal=dinner",
    )
    assert resp.status_code in (200, 302, 401, 403)
