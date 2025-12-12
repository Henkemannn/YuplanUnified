import pytest
from sqlalchemy import text


def _seed_site_and_departments(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL);
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT NOT NULL,
            resident_count_mode TEXT NOT NULL,
            resident_count_fixed INTEGER NOT NULL DEFAULT 0
        );
    """))
    site_id = "site-1"
    db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": "Testplats"})
    db.execute(text("INSERT OR IGNORE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) VALUES(:i,:s,:n,'manual',:f)"), {"i": "dep-A", "s": site_id, "n": "Avd A", "f": 10})
    db.execute(text("INSERT OR IGNORE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) VALUES(:i,:s,:n,'manual',:f)"), {"i": "dep-B", "s": site_id, "n": "Avd B", "f": 8})
    return site_id


def _seed_diet_types(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS dietary_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_select INTEGER NOT NULL DEFAULT 0
        );
    """))
    db.execute(text("INSERT INTO dietary_types(tenant_id,name,default_select) VALUES(1,'Normalkost',0)"))
    db.execute(text("INSERT INTO dietary_types(tenant_id,name,default_select) VALUES(1,'Gluten',0)"))
    db.execute(text("INSERT INTO dietary_types(tenant_id,name,default_select) VALUES(1,'Laktos',0)"))


def _seed_diet_defaults(db):
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS department_diet_defaults (
            department_id TEXT NOT NULL,
            diet_type_id TEXT NOT NULL,
            default_count INTEGER NOT NULL DEFAULT 0,
            always_mark INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (department_id, diet_type_id)
        )
        """
    ))
    # For Avd A: 1 Gluten + 1 Laktos defaults (names align with marks)
    db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES('dep-A','Gluten',1)"))
    db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES('dep-A','Laktos',1)"))


def _seed_weekview(db, year: int, week: int):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_registrations (
          tenant_id TEXT NOT NULL,
          department_id TEXT NOT NULL,
          year INTEGER NOT NULL,
          week INTEGER NOT NULL,
          day_of_week INTEGER NOT NULL,
          meal TEXT NOT NULL,
          diet_type TEXT NOT NULL,
          marked INTEGER NOT NULL DEFAULT 0,
          UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
        );
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_versions (
          tenant_id TEXT NOT NULL,
          department_id TEXT NOT NULL,
          year INTEGER NOT NULL,
          week INTEGER NOT NULL,
          version INTEGER NOT NULL DEFAULT 0,
          UNIQUE (tenant_id, department_id, year, week)
        );
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_residents_count (
            tenant_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            meal TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (tenant_id, department_id, year, week, day_of_week, meal)
        );
    """))
    for dep in ("dep-A", "dep-B"):
        db.execute(text("INSERT OR IGNORE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1',:d,:y,:w,0)"), {"d": dep, "y": year, "w": week})
    for dow in range(1, 8):
        for meal in ("lunch", "dinner"):
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count(tenant_id,department_id,year,week,day_of_week,meal,count) VALUES('1','dep-A',:y,:w,:d,:m,:c)"), {"y": year, "w": week, "d": dow, "m": meal, "c": 10})
            count_b = 6 if (dow == 3 and meal == "lunch") else 8
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count(tenant_id,department_id,year,week,day_of_week,meal,count) VALUES('1','dep-B',:y,:w,:d,:m,:c)"), {"y": year, "w": week, "d": dow, "m": meal, "c": count_b})
    # Specials for Avd A
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Gluten',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Laktos',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Normalkost',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,2,'lunch','Gluten',1)"), {"y": year, "w": week})
    # Avd B Sunday dinner 0 residents
    db.execute(text("UPDATE weekview_residents_count SET count=0 WHERE tenant_id='1' AND department_id='dep-B' AND year=:y AND week=:w AND day_of_week=7 AND meal='dinner'"), {"y": year, "w": week})


def test_seeded_weekly_diets_report(client):
    year, week = 2025, 10
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "site-1"
    from core.db import get_session
    db = get_session()
    try:
        _seed_site_and_departments(db)
        _seed_diet_types(db)
        _seed_weekview(db, year, week)
        _seed_diet_defaults(db)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=ALL&view=day")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Avd A" in html and "Avd B" in html
    assert "Boende Lunch" in html and "Lunch – Special" in html and "Lunch – Normal" in html
    assert "Boende Kväll" in html and "Kväll – Special" in html and "Kväll – Normal" in html
    assert ">10<" in html
    assert ">2<" in html
    assert ">8<" in html

    resp2 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=ALL&view=week")
    assert resp2.status_code == 200
    html2 = resp2.get_data(as_text=True)
    assert "Avd A" in html2
    assert ">3<" in html2
    assert ">67<" in html2
    assert ">0<" in html2
    assert ">70<" in html2

    resp3 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=dep-A&view=week")
    assert resp3.status_code == 200
    html3 = resp3.get_data(as_text=True)
    assert "Avd A" in html3 and "Avd B" not in html3

    resp4 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=dep-B&view=day")
    assert resp4.status_code == 200
    html4 = resp4.get_data(as_text=True)
    assert ">6<" in html4
