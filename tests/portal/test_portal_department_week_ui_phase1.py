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
    # Monday data
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'lunch',10)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'dinner',8)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Gluten',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Laktos',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    # Alt2 choice storage
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)"), {"s": site_id, "d": dept_id, "w": week})
    # Menu service tables
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=301"))
    db.execute(text("DELETE FROM menus WHERE id=301"))
    db.execute(text("DELETE FROM dishes WHERE id IN (201,202,203,204)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(201,1,'Pannbiff',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(202,1,'Köttbullar',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(203,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(204,1,'Kvällsgröt',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year) VALUES(301,1,:w,:y)"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(301,'mon','lunch','alt1',201)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(301,'mon','lunch','alt2',202)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(301,'mon','dessert','dessert',203)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(301,'mon','dinner','dinner',204)"))
    db.commit()


def test_portal_department_week_ui_renders_page(client_admin):
    year = 2025
    week = 47
    dept_id = "22222222-3333-4444-5555-666666666666"
    site_id = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
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
    assert "Vecka 47" in html
    assert "Avd 1" in html
    assert "Faktaruta" in html
    assert "Inga risrätter" in html
    assert "Pannbiff" in html or "Köttbullar" in html
    assert "Valda dagar:" in html
    assert "portal-alt-selected" in html  # Monday Alt2 highlight
    assert "Gluten" in html or "Laktos" in html