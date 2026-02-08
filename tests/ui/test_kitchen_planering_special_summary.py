from datetime import date as _date
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal(site_id: str, dept_id: str, year: int, week: int, lunch_residents: int, diet_name: str, diet_count: int):
    from core.db import get_session
    from core.weekview.repo import WeekviewRepo
    from core.admin_repo import DietTypesRepo
    db = get_session()
    try:
        # sites
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i,'Test Site',0)"), {"i": site_id})
        # departments
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS departments (
              id TEXT PRIMARY KEY,
              site_id TEXT NOT NULL,
              name TEXT NOT NULL,
              resident_count_mode TEXT NOT NULL,
              resident_count_fixed INTEGER NOT NULL DEFAULT 0,
              notes TEXT NULL,
              version INTEGER NOT NULL DEFAULT 0
            )
            """
        ))
        db.execute(text(
            "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)\n             VALUES(:id, :s, 'Avd 1', 'fixed', :rc, 0)"
        ), {"id": dept_id, "s": site_id, "rc": lunch_residents})
        db.commit()
    finally:
        db.close()
    # Create dietary type and defaults via repos to keep portability
    types_repo = DietTypesRepo()
    dt_id = types_repo.create(site_id=site_id, name=diet_name, default_select=False)
    # Insert default count for department
    db = get_session()
    try:
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
        db.execute(text(
            "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count)\n             VALUES(:d, :t, :c)"
        ), {"d": dept_id, "t": str(dt_id), "c": diet_count})
        db.commit()
    finally:
        db.close()
    # Mark Monday lunch for this diet
    repo = WeekviewRepo()
    repo.apply_operations(tenant_id=1, year=year, week=week, department_id=dept_id, ops=[
        {"day_of_week": 1, "meal": "lunch", "diet_type": str(dt_id), "marked": True}
    ])
    return dt_id


def test_special_summary_totals_and_done(app_session):
    client = app_session.test_client()
    site_id = "site-plan-2"
    dept_id = "dept-plan-2"
    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]
    dt_id = _seed_minimal(site_id, dept_id, year, week, lunch_residents=10, diet_name="Laktosfri", diet_count=4)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=lunch&mode=special&show_results=1", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Overview numbers must reflect totals and done
    assert ">Totalt special:" in html
    assert ">Klart (markerat):" in html
    # Totals table must include the diet name and counts
    assert "Specialkost – sammanställning" in html
    assert "Laktosfri" in html
    assert ">4<" in html  # total count
    # Since marked for Monday lunch, done should equal 4 for this single department
    assert ">4</td>" in html or ">4</div>" in html
