import re
from sqlalchemy import text

def _seed(db, dept_id: str, site_id: str, year: int, week: int):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            notes TEXT NULL,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
    """))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s,:n,:note,'manual')"), {"i": dept_id, "s": site_id, "n": "Avd 1", "note": "Info"})
    # Menu + choice storage
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER, status TEXT NOT NULL DEFAULT 'draft')"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=901"))
    db.execute(text("DELETE FROM menus WHERE id=901"))
    db.execute(text("DELETE FROM dishes WHERE id IN (801,802)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(801,1,'Raggmunk',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(802,1,'Ärtsoppa',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year,status) VALUES(901,1,:w,:y,'draft')"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(901,'mon','lunch','alt1',801)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(901,'mon','lunch','alt2',802)"))
    # Choice mapping table (alt2_flags) mark Monday Alt2 so selected_alt=Alt2
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)"), {"s": site_id, "d": dept_id, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS department_menu_choices(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, meal TEXT NOT NULL DEFAULT 'lunch', selected_variant TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT, UNIQUE(tenant_id,site_id,department_id,year,week,weekday,meal))"))
    db.execute(text("INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES(1,:s,:d,:y,:w,1,'lunch','alt2',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"s": site_id, "d": dept_id, "y": year, "w": week})
    db.commit()

def test_portal_department_week_ui_phase4(client_admin):
    year=2025; week=12
    dept_id="10101010-2020-3030-4040-505050505050"; site_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    from core.db import get_session
    db=get_session()
    try:
        _seed(db, dept_id, site_id, year, week)
    finally:
        db.close()
    resp = client_admin.get(f"/ui/portal/department/week?year={year}&week={week}", environ_overrides={"test_claims": {"department_id": dept_id}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "portal-week-status" in html
    assert "portal-week-status-label" in html and "Valda dagar:" in html
    dot_count = len(re.findall(r"portal-week-dot", html))
    assert dot_count >= 7
    assert "portal-week-dot chosen" in html
    assert re.search(r"\b[0-7]\s*/\s*7\b", html)
