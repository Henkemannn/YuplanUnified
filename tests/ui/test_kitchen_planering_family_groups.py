from datetime import date as _date

from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_planering_specialkost_renders_family_groups_only(app_session):
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    from core.weekview.repo import WeekviewRepo

    site_id = "site-plan-family"
    dept_id = "dept-plan-family"

    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i, 'Family Site', 0)"), {"i": site_id})
        db.execute(
            text(
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
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                "VALUES(:id, :s, 'Avd Fam', 'fixed', 12, 0)"
            ),
            {"id": dept_id, "s": site_id},
        )
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS department_diet_defaults (
                  department_id TEXT NOT NULL,
                  diet_type_id TEXT NOT NULL,
                  default_count INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY (department_id, diet_type_id)
                )
                """
            )
        )
        db.commit()
    finally:
        db.close()

    repo = DietTypesRepo()
    dt_textur = repo.create(site_id=site_id, name="Timbal", diet_family="Textur", default_select=False)
    dt_allergy = repo.create(site_id=site_id, name="Glutenfri", diet_family="Allergi / Exkludering", default_select=False)
    dt_choice = repo.create(site_id=site_id, name="Vegan", diet_family="Kostval", default_select=False)

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) "
                "VALUES(:d, :t, :c)"
            ),
            {"d": dept_id, "t": str(dt_textur), "c": 2},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) "
                "VALUES(:d, :t, :c)"
            ),
            {"d": dept_id, "t": str(dt_allergy), "c": 2},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) "
                "VALUES(:d, :t, :c)"
            ),
            {"d": dept_id, "t": str(dt_choice), "c": 1},
        )
        db.commit()
    finally:
        db.close()

    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]
    WeekviewRepo().apply_operations(
        tenant_id=1,
        year=year,
        week=week,
        department_id=dept_id,
        ops=[
            {"day_of_week": 1, "meal": "lunch", "diet_type": str(dt_textur), "marked": True},
            {"day_of_week": 1, "meal": "lunch", "diet_type": str(dt_allergy), "marked": True},
            {"day_of_week": 1, "meal": "lunch", "diet_type": str(dt_choice), "marked": True},
        ],
    )

    client = app_session.test_client()
    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=lunch&mode=special",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    assert "Textur" in html
    assert "Allergi / Exkludering" in html
    assert "Kostval" in html
    assert "data-family=\"Textur\"" in html
    assert "data-family=\"Allergi / Exkludering\"" in html
    assert "data-family=\"Kostval\"" in html

    assert "Visa alla specialkoster" not in html
    assert "kp-chip-grid--compact" not in html
    assert "kp-chip-grid--all" not in html
