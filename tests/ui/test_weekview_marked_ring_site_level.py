from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal_marked():
    from core.db import get_session
    conn = get_session()
    try:
        # Ensure schema
        conn.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations (tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS weekview_versions (tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, version INTEGER, UNIQUE(tenant_id,department_id,year,week))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT, diet_type_id TEXT, default_count INTEGER, PRIMARY KEY (department_id, diet_type_id))"))
        # Seed site + department
        site_id = '00000000-0000-0000-0000-000000000000'
        dep_id = '00000000-0000-0000-0000-000000000001'
        site = conn.execute(text("SELECT id FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, 'Test Site')"), {"sid": site_id})
        dep = conn.execute(text("SELECT id FROM departments WHERE id=:did"), {"did": dep_id}).fetchone()
        if not dep:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, 'Avd Alpha', 'fixed', 5)"), {"did": dep_id, "sid": site_id})
        # Ensure a diet default so row renders; use diet_type_id 'Gluten'
        dd = conn.execute(text("SELECT 1 FROM department_diet_defaults WHERE department_id=:d AND diet_type_id='Gluten'"), {"d": dep_id}).fetchone()
        if not dd:
            conn.execute(text("INSERT INTO department_diet_defaults (department_id, diet_type_id, default_count) VALUES (:d, 'Gluten', 1)"), {"d": dep_id})
        # Insert a marked registration: Monday lunch Gluten
        year, week = 2026, 8
        conn.execute(text("INSERT OR REPLACE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1',:d,:y,:w,0)"), {"d": dep_id, "y": year, "w": week})
        conn.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1',:d,:y,:w,1,'lunch','Gluten',1)"), {"d": dep_id, "y": year, "w": week})
        conn.commit()
        return site_id, dep_id, year, week
    finally:
        conn.close()


def test_weekview_site_level_marked_ring(app_session):
    client = app_session.test_client()
    site_id, _dep, year, week = _seed_minimal_marked()
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Marked cell present
    assert 'diet-cell marked' in html
    # CSS selector present in unified_ui.css
    with open('static/unified_ui.css', 'r', encoding='utf-8') as f:
        css = f.read()
    assert '.weekview-all .weekview td.diet-cell.marked::before' in css
