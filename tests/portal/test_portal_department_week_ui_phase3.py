from sqlalchemy import text


def _seed(db, dept_id: str, site_id: str, year: int, week: int):
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
    # Minimal menu + flags for one day
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))"))
    db.execute(text("INSERT OR REPLACE INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)"), {"t":1, "d":dept_id, "y":year, "w":week})
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)"), {"s": site_id, "d": dept_id, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=601"))
    db.execute(text("DELETE FROM menus WHERE id=601"))
    db.execute(text("DELETE FROM dishes WHERE id IN (501,502,503,504)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(501,1,'Pannbiff',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(502,1,'Köttbullar',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(503,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(504,1,'Kvällsgröt',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year) VALUES(601,1,:w,:y)"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','lunch','alt1',501)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','lunch','alt2',502)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','dessert','dessert',503)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','dinner','dinner',504)"))
    db.commit()


def test_portal_department_week_ui_has_menu_popup_markup(client_admin):
    year=2025; week=47
    dept_id="55555555-6666-7777-8888-999999999999"; site_id="eeeeeeee-ffff-0000-1111-222222222222"
    from core.db import get_session
    db=get_session()
    try:
        _seed(db, dept_id, site_id, year, week)
    finally:
        db.close()
    resp = client_admin.get(f"/ui/portal/department/week?year={year}&week={week}", environ_overrides={"test_claims": {"department_id": dept_id}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<th>Meny</th>" in html
    assert "class=\"portal-menu-btn\"" in html or "class=\"portal-menu-btn portal-menu-btn" in html
    assert "data-kvallsmat=" in html
    assert "id=\"portal-menu-overlay\"" in html
    assert "Kvällsmat</h3>" in html
