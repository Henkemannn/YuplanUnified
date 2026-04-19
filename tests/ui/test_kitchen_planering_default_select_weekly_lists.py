import re

from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_department_and_diet(site_id: str, dep_id: str, diet_name: str, default_select: bool) -> str:
    from core.db import get_session
    from core.admin_repo import DepartmentsRepo, DietTypesRepo

    db = get_session()
    try:
        db.execute(
            text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)")
        )
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
            text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i, :n, 0)"),
            {"i": site_id, "n": "Site Default Select"},
        )
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)
                VALUES(:id, :s, 'Avd DS', 'fixed', 10, 0)
                """
            ),
            {"id": dep_id, "s": site_id},
        )
        db.commit()
    finally:
        db.close()

    trepo = DietTypesRepo()
    diet_id = str(trepo.create(site_id=site_id, name=diet_name, default_select=default_select))

    drepo = DepartmentsRepo()
    version = drepo.get_version(dep_id) or 0
    drepo.upsert_department_diet_defaults(dep_id, version, [{"diet_type_id": diet_id, "default_count": 2}])
    return diet_id


def test_default_select_true_preselects_special_chip_in_weekly_list(app_session):
    client = app_session.test_client()
    site_id = "site-default-select-true"
    dep_id = "dep-default-select-true"
    diet_id = _seed_site_department_and_diet(site_id, dep_id, "Laktos DS", default_select=True)

    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&year=2026&week=8&day=0&meal=lunch&mode=special",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    assert f'data-diet-id="{diet_id}"' in html
    assert re.search(r'class="[^"]*js-special-chip[^"]*active[^"]*"', html)


def test_default_select_false_does_not_preselect_special_chip_in_weekly_list(app_session):
    client = app_session.test_client()
    site_id = "site-default-select-false"
    dep_id = "dep-default-select-false"
    diet_id = _seed_site_department_and_diet(site_id, dep_id, "Gluten DS", default_select=False)

    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&year=2026&week=8&day=0&meal=lunch&mode=special",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    assert f'data-diet-id="{diet_id}"' in html
    assert not re.search(r'class="[^"]*js-special-chip[^"]*active[^"]*"', html)
