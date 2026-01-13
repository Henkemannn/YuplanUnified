from sqlalchemy import text


def _seed_portal_week(db, dept_id: str, site_id: str, year: int, week: int):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
    """))
    db.execute(text("CREATE TABLE IF NOT EXISTS department_notes(department_id TEXT PRIMARY KEY, notes TEXT)"))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,:n,'manual')"), {"i": dept_id, "s": site_id, "n": "Avd 1"})
    db.execute(text("INSERT OR REPLACE INTO department_notes(department_id, notes) VALUES(:i,:n)"), {"i": dept_id, "n": "Inga risrätter"})
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))"))
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'lunch',10)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.commit()


def test_portal_department_week_ui_phase7_sync_indicator_present(client_admin):
    year = 2025
    week = 48
    dept_id = "33333333-4444-5555-6666-777777777777"
    site_id = "cccccccc-dddd-eeee-ffff-000000000000"
    from core.db import get_session
    db = get_session()
    try:
        _seed_portal_week(db, dept_id, site_id, year, week)
    finally:
        db.close()
    resp = client_admin.get(
        f"/ui/portal/department/week?year={year}&week={week}",
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="portal-sync-indicator"' in html
    assert 'Synkad' in html
