from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal(site_id: str, dept_id: str):
    from core.db import get_session
    from core.admin_repo import DietTypesRepo
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i,'Test Site',0)"), {"i": site_id})
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
            "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)\n             VALUES(:id, :s, 'Avd 1', 'fixed', 10, 0)"
        ), {"id": dept_id, "s": site_id})
        db.commit()
    finally:
        db.close()
    types_repo = DietTypesRepo()
    dt_id = types_repo.create(site_id=site_id, name="Glutenfri", default_select=False)
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
            "INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count)\n             VALUES(:d, :t, 3)"
        ), {"d": dept_id, "t": str(dt_id)})
        db.commit()
    finally:
        db.close()
    return dt_id


def test_special_chips_present(app_session):
    client = app_session.test_client()
    site_id = "site-plan-chips"
    dept_id = "dept-plan-chips"
    _seed_minimal(site_id, dept_id)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&mode=special", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "js-special-chip" in html
    assert "data-diet-id" in html
