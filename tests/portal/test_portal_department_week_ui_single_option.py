from sqlalchemy import text


def _seed_single_option_week(db, dept_id: str, site_id: str, year: int, week: int):
    db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            notes TEXT NULL,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
    """))
    db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:s, 'Site', 1, 0)"), {"s": site_id})
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s,:n,:note,'manual')"), {"i": dept_id, "s": site_id, "n": "Avd 1", "note": "Inga risrätter"})
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER, status TEXT NOT NULL DEFAULT 'draft')"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=811"))
    db.execute(text("DELETE FROM menus WHERE id=811"))
    db.execute(text("DELETE FROM dishes WHERE id IN (711,712,713,714)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(711,1,'Pannbiff',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(712,1,'Köttbullar',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(713,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(714,1,'Kvällsgröt',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year,status) VALUES(811,1,:w,:y,'draft')"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(811,'mon','lunch','alt1',711)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(811,'mon','lunch','alt2',712)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(811,'mon','dessert','dessert',713)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(811,'mon','dinner','dinner',714)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(811,'tue','lunch','alt1',711)"))
    db.commit()


def test_portal_department_week_ui_single_option_helper_row(client_admin):
    year = 2025
    week = 47
    dept_id = "22222222-3333-4444-5555-666666666668"
    site_id = "bbbbbbbb-cccc-dddd-eeee-fffffffffff1"
    from core.db import get_session

    db = get_session()
    try:
        _seed_single_option_week(db, dept_id, site_id, year, week)
    finally:
        db.close()

    resp = client_admin.get(
        f"/ui/portal/department/week?year={year}&week={week}",
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Endast ett lunchalternativ idag" in html
    assert "portal-day-row__info-row" in html
    assert 'aria-hidden="true"' in html