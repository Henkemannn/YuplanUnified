from flask.testing import FlaskClient
from sqlalchemy import text

def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _seed(db, site_id: str, dep_id: str, date_str: str):
    db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
    db.execute(text("INSERT OR REPLACE INTO sites(id, name) VALUES(:i,'Site')"), {"i": site_id})
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,'Dept','manual')"), {"i": dep_id, "s": site_id})
    # Minimal menu + residents via Weekview backing tables
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', updated_at TEXT)"))
    db.execute(text("INSERT INTO menus(id, tenant_id, year, week, status, updated_at) VALUES(1,1,2025,47,'draft','2025-11-20T12:00:00Z')"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(menu_id INTEGER, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    # Insert alt1/alt2 for lunch and alt1 for dinner
    for day in ["Måndag"]:
        db.execute(text("INSERT OR REPLACE INTO menu_variants(menu_id, day, meal, variant_type, dish_id) VALUES(1,:d,'Lunch','alt1',NULL)"), {"d": day})
        db.execute(text("INSERT OR REPLACE INTO menu_variants(menu_id, day, meal, variant_type, dish_id) VALUES(1,:d,'Lunch','alt2',NULL)"), {"d": day})
        db.execute(text("INSERT OR REPLACE INTO menu_variants(menu_id, day, meal, variant_type, dish_id) VALUES(1,:d,'Kväll','alt1',NULL)"), {"d": day})
    # Residents
    db.execute(text("CREATE TABLE IF NOT EXISTS residents_counts(site_id TEXT, department_id TEXT, date TEXT, lunch INTEGER, dinner INTEGER)"))
    db.execute(text("INSERT OR REPLACE INTO residents_counts(site_id, department_id, date, lunch, dinner) VALUES(:s,:d,:dt,10,8)"), {"s": site_id, "d": dep_id, "dt": date_str})
    # Diet registrations (specialkost) for lunch only
    db.execute(text("CREATE TABLE IF NOT EXISTS diet_registrations(site_id TEXT, department_id TEXT, date TEXT, meal TEXT, diet_type_id TEXT, count INTEGER)"))
    db.execute(text("INSERT OR REPLACE INTO diet_registrations(site_id, department_id, date, meal, diet_type_id, count) VALUES(:s,:d,:dt,'lunch','veg',3)"), {"s": site_id, "d": dep_id, "dt": date_str})
    db.commit()


def test_planera_day_payload_and_ui(client_admin: FlaskClient):
    from core.db import get_session
    from datetime import date
    db = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000111"
        dep_id = "00000000-0000-0000-0000-000000000222"
        d = date.fromisocalendar(2025, 47, 1).isoformat()  # Monday in week 47
        _seed(db, site_id, dep_id, d)
    finally:
        db.close()
    # Request unified UI variant
    resp = client_admin.get(
        f"/ui/planera/day?site_id={site_id}&department_id={dep_id}&date={d}&ui=unified",
        headers=_h("cook"),
    )
    assert resp.status_code in (200, 302)
    if resp.status_code == 302:
        resp = client_admin.get(resp.headers.get("Location", ""), headers=_h("cook"))
    html = resp.get_data(as_text=True)
    # Stable invariants for Phase 1: context and counts
    assert ("M\u00e5ltidsvy" in html) or ("Planera" in html)
    assert "Site" in html
    assert "Dept" in html or "Avdelning" in html
    # Meal labels present (Lunch/Kväll)
    assert ("Lunch" in html) or ("Kv\u00e4ll" in html) or ("Kväll" in html)
    # Counts
    assert "Boende:" in html
    assert "Specialkost:" in html
    assert "Normalkost:" in html
    # No write forms in Phase 1
    assert "<form" not in html
