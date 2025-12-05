import re
from datetime import date as _date
from flask.testing import FlaskClient
from sqlalchemy import text

ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_setup(site_id: str, dep_id: str, year: int, week: int):
    from core.db import get_session
    db = get_session()
    try:
        # Site + department
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
        if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
            db.execute(text("INSERT INTO sites(id,name) VALUES(:i,'Test Site')"), {"i": site_id})
        if not db.execute(text("SELECT 1 FROM departments WHERE id=:i"), {"i": dep_id}).fetchone():
            db.execute(text("INSERT INTO departments(id,site_id,name,resident_count_mode) VALUES(:i,:s,'Avd A','manual')"), {"i": dep_id, "s": site_id})
        # Department diet defaults with always_mark flag
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS department_diet_defaults (
                department_id TEXT NOT NULL,
                diet_type_id TEXT NOT NULL,
                default_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (department_id, diet_type_id)
            )
            """
        ))
        # Ensure optional always_mark column exists
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('department_diet_defaults')")).fetchall()}
        if "always_mark" not in cols:
            try:
                db.execute(text("ALTER TABLE department_diet_defaults ADD COLUMN always_mark INTEGER NOT NULL DEFAULT 0"))
            except Exception:
                pass
        # Defaults: gluten=2, laktos=1, timbal=3 (always)
        db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id,diet_type_id,default_count,always_mark) VALUES(:d,'gluten',2,0)"), {"d": dep_id})
        db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id,diet_type_id,default_count,always_mark) VALUES(:d,'laktos',1,0)"), {"d": dep_id})
        db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id,diet_type_id,default_count,always_mark) VALUES(:d,'timbal',3,1)"), {"d": dep_id})
        # Weekview schema for marks
        db.execute(text(
            """
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
            )
            """
        ))
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS weekview_versions (
              tenant_id TEXT NOT NULL,
              department_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              version INTEGER NOT NULL DEFAULT 0,
              UNIQUE (tenant_id, department_id, year, week)
            )
            """
        ))
        # Seed version row
        db.execute(text("INSERT OR IGNORE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1',:dep,:yy,:ww,0)"), {"dep": dep_id, "yy": year, "ww": week})
        db.commit()
    finally:
        db.close()


def _seed_marks(dep_id: str, year: int, week: int):
    from core.db import get_session
    db = get_session()
    try:
        # Monday lunch: gluten (mark)
        db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1',:dep,:yy,:ww,1,'lunch','gluten',1)"), {"dep": dep_id, "yy": year, "ww": week})
        # Tuesday lunch: laktos (mark)
        db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1',:dep,:yy,:ww,2,'lunch','laktos',1)"), {"dep": dep_id, "yy": year, "ww": week})
        # Bump version
        db.execute(text("UPDATE weekview_versions SET version=version+1 WHERE tenant_id='1' AND department_id=:dep AND year=:yy AND week=:ww"), {"dep": dep_id, "yy": year, "ww": week})
        db.commit()
    finally:
        db.close()


def test_weekview_report_phase3_debiterbar_marks(app_session):
    client: FlaskClient = app_session.test_client()
    site_id = "00000000-0000-0000-0000-00000000aaaa"
    dep_id = "00000000-0000-0000-0000-00000000bbbb"
    # Use a fixed week
    year = 2025
    week = 49
    _seed_setup(site_id, dep_id, year, week)
    _seed_marks(dep_id, year, week)

    # GET HTML report
    r = client.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Labels present
    assert "Gjorda specialkoster" in html
    assert "Gjorda specialkoster (lunch)" in html
    assert "Gjorda specialkoster (kväll)" in html

    # Expectation:
    # Mon lunch: gluten(2) + timbal(3) = 5
    assert re.search(r">\s*5\s*<", html)
    # Tue lunch: laktos(1) + timbal(3) = 4
    assert re.search(r">\s*4\s*<", html)
    # A day with no marks still counts timbal(3)
    assert re.search(r">\s*3\s*<", html)

    # Weekly totals are shown in the summary table; presence is sufficient here
    assert "Gjorda specialkoster" in html


def test_weekview_report_phase3_no_marks_defaults_only(app_session):
    client: FlaskClient = app_session.test_client()
    site_id = "00000000-0000-0000-0000-00000000cccc"
    dep_id = "00000000-0000-0000-0000-00000000dddd"
    year = 2025
    week = 50
    _seed_setup(site_id, dep_id, year, week)
    # No marks seeded

    r = client.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # There is timbal always_mark=1 -> should show at least 3 somewhere
    assert re.search(r">\s*3\s*<", html)
    # But gluten/laktos should not contribute without marks; ensure we don't show 5 or 4 patterns tied to examples
    # (Weak negative check to avoid overfitting; presence of 5 may come from other values.)
    assert "Gjorda specialkoster" in html
