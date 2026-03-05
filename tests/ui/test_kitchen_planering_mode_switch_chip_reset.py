from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_diet(site_id: str) -> str:
    from core.admin_repo import DietTypesRepo, DepartmentsRepo

    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id, "Avd Isolering", "fixed", 10)
    trepo = DietTypesRepo()
    diet_id = str(trepo.create(site_id=site_id, name="Laktos", default_select=False))
    version = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], version, [{"diet_type_id": diet_id, "default_count": 2}])
    return diet_id


def _insert_normal_exclusion(site_id: str, year: int, week: int, day_index: int, meal: str, alt: str, diet_type_id: str) -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text(
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
            )
        )
        db.execute(
            text(
                """
                INSERT OR IGNORE INTO normal_exclusions(tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
                VALUES (:tid, :s, :y, :w, :d, :m, :a, :dt)
                """
            ),
            {"tid": "1", "s": site_id, "y": year, "w": week, "d": day_index, "m": meal, "a": alt, "dt": diet_type_id},
        )
        db.commit()
    finally:
        db.close()


def test_switch_normal_to_special_does_not_carry_chip_state(app_session):
    client = app_session.test_client()
    site_id = "site-chip-switch-isolation"
    diet_id = _seed_site_and_diet(site_id)
    year = 2026
    week = 8
    day_index = 1

    # Simulate a toggled normal chip (active in normal view).
    _insert_normal_exclusion(site_id, year, week, day_index, "lunch", "1", diet_id)

    rv_normal = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv_normal.status_code == 200
    html_normal = rv_normal.data.decode("utf-8")
    assert "js-normal-chip active" in html_normal

    # Switch to special view: no implicit carry-over from normal chip state.
    rv_special = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=special&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv_special.status_code == 200
    html_special = rv_special.data.decode("utf-8")
    assert "js-special-chip active" not in html_special
    assert "Välj specialkoster ovan för att bygga arbetslistan." in html_special
