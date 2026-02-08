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
        # diet types (site-scoped)
        # use repo to ensure table exists
        db.commit()
    finally:
        db.close()
    # Create dietary type and defaults via repos to keep portability
    types_repo = DietTypesRepo()
    dt_id = types_repo.create(site_id=site_id, name=diet_name, default_select=False)
    # Insert default count for department
    db = get_session()
    try:
        # Ensure table exists minimally
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
        # Check if always_mark column exists; add if missing is out-of-scope, so adapt insert
        try:
            cols = db.execute(text("PRAGMA table_info('department_diet_defaults')")).fetchall()
            has_always = any(str(c[1]) == 'always_mark' for c in cols)
        except Exception:
            has_always = False
        if has_always:
            db.execute(text(
                "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count, always_mark)\n                 VALUES(:d, :t, :c, 0)"
            ), {"d": dept_id, "t": str(dt_id), "c": diet_count})
        else:
            db.execute(text(
                "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count)\n                 VALUES(:d, :t, :c)"
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


def test_planering_summary_numbers(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    dept_id = "dept-plan-1"
    # Use a stable week/year
    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]
    dt_id = _seed_minimal(site_id, dept_id, year, week, lunch_residents=10, diet_name="Glutenfri", diet_count=3)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=lunch&selected_diets={dt_id}&show_results=1", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Totals cards must show numbers
    assert ">10<" in html or ">10</div>" in html
    assert ">3<" in html
    # Normal = 7
    assert ">7<" in html
    # Special summary table should include diet name and counts
    assert "Specialkost – sammanställning" in html
    assert "Glutenfri" in html
