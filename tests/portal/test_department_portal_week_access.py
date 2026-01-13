from datetime import datetime
from sqlalchemy import text


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


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
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'dinner',8)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Gluten',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Laktos',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,2,'lunch',12)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)"), {"s": site_id, "d": dept_id, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=201"))
    db.execute(text("DELETE FROM menus WHERE id=201"))
    db.execute(text("DELETE FROM dishes WHERE id IN (101,102,103,104)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(101,1,'Pannbiff med lök',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(102,1,'Fiskgratäng',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(103,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(104,1,'Kvällsgröt',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year) VALUES(201,1,:w,:y)"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','lunch','alt1',101)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','lunch','alt2',102)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','dessert','dessert',103)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','dinner','dinner',104)"))
    db.commit()


def test_portal_week_endpoint_populate(client_admin):
    year = 2025
    week = 47
    dept_id = "11111111-2222-3333-4444-555555555555"
    site_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    from core.db import get_session
    db = get_session()
    try:
        _seed_portal_week(db, dept_id, site_id, year, week)
    finally:
        db.close()
    r1 = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    data = r1.get_json()
    assert data["department_id"] == dept_id
    assert data["facts"]["note"] == "Inga risrätter"
    assert data["progress"]["total_days"] == 7
    monday = data["days"][0]
    assert monday["flags"]["alt2_lunch"] is True
    assert monday["choice"]["selected_alt"] == "Alt2"
    lunch_diets = monday["diets_summary"]["lunch"]
    diet_names = {d["diet_name"] for d in lunch_diets}
    assert {"Gluten", "Laktos"}.issubset(diet_names)
    menu_mon = monday["menu"]
    assert menu_mon["lunch_alt1"] == "Pannbiff med lök"
    assert menu_mon["lunch_alt2"] == "Fiskgratäng"
    assert menu_mon["dessert"] == "Fruktsallad"
    assert menu_mon["dinner"] == "Kvällsgröt"
    tuesday = data["days"][1]
    assert tuesday["choice"]["selected_alt"] == "Alt1"
    assert tuesday["diets_summary"]["lunch"] == []
    menu_tue = tuesday["menu"]
    assert menu_tue["lunch_alt1"] is None
    assert menu_tue["lunch_alt2"] is None
    assert menu_tue["dessert"] is None
    assert menu_tue["dinner"] is None
    assert data["progress"]["days_with_choice"] >= 1
    assert etag and etag.startswith('W/"portal-dept-week:')
    r2 = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers={**_h(), "If-None-Match": etag},
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert r2.status_code == 304
    assert r2.get_data() in (b"", b"\n")
    assert r2.headers.get("ETag") == etag


def test_portal_week_basic_access(client_admin):
    from core.db import get_session
    dept_id = "55555555-2222-3333-4444-111111111111"
    site_id = "zzzzzzzz-bbbb-cccc-dddd-yyyyyyyyyyyy"
    db = get_session()
    try:
        _seed_portal_week(db, dept_id, site_id, 2025, 47)
    finally:
        db.close()
    resp_ok = client_admin.get(
        "/portal/department/week?year=2025&week=47",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp_ok.status_code == 200