from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_diets(site_id: str):
    from core.admin_repo import SitesRepo, DietTypesRepo, DepartmentsRepo
    srepo = SitesRepo(); srepo.create_site("Render Site")
    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id, "Avd A", "fixed", 10)
    trepo = DietTypesRepo()
    diet_id = trepo.create(site_id=site_id, name="Laktos", default_select=False)
    # Add a default count so diet_options contains this diet
    v = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], v, [{"diet_type_id": str(diet_id), "default_count": 2}])
    return str(diet_id)


def _insert_exclusion(site_id: str, year: int, week: int, day_index: int, meal: str, alt: str, diet_type_id: str):
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS normal_exclusions (
              tenant_id TEXT NOT NULL,
              site_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_index INTEGER NOT NULL,
              meal TEXT NOT NULL,
              alt TEXT NOT NULL,
              diet_type_id TEXT NOT NULL,
              UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
            );
            """
        ))
        db.execute(text(
            """
            INSERT OR IGNORE INTO normal_exclusions(tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
            VALUES (:tid, :s, :y, :w, :d, :m, :a, :dt)
            """
        ), {"tid": "1", "s": site_id, "y": year, "w": week, "d": day_index, "m": meal, "a": alt, "dt": diet_type_id})
        db.commit()
    finally:
        db.close()


def test_planering_renders_active_chips_from_db(app_session):
    client = app_session.test_client()
    site_id = "site-normal-exc-render-1"
    diet_id = _seed_site_and_diets(site_id)
    # Choose a fixed week/day for deterministic tests
    year = 2026; week = 6; day_index = 3
    _insert_exclusion(site_id, year, week, day_index, "lunch", "1", diet_id)

    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Ensure Alt 1 group present and at least one active chip rendered
    assert 'aria-label="Specialkoster – Alt 1"' in html
    assert 'class="diet-chip active"' in html
