from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_deps(site_id: str):
    from core.admin_repo import DepartmentsRepo
    drepo = DepartmentsRepo()
    dep1, _ = drepo.create_department(site_id, "Avd A", "fixed", 10)
    dep2, _ = drepo.create_department(site_id, "Avd B", "fixed", 7)
    return dep1["id"], dep2["id"]


def _ensure_alt2_for_dep(department_id: str, site_id: str, year: int, week: int, day_index: int):
    # Directly set alt2 flag for the given department/day in SQLite
    from core.weekview.repo import WeekviewRepo
    repo = WeekviewRepo()
    repo.set_alt2_flags(tenant_id=1, year=year, week=week, department_id=department_id, days=[day_index], site_id=site_id)



def test_planering_normal_baselines_ids_and_values(app_session):
    from core.admin_repo import SitesRepo, DietTypesRepo
    srepo = SitesRepo(); site, _ = srepo.create_site("Totals Baseline Site")
    site_id = site["id"]
    dep1_id, dep2_id = _seed_site_deps(site_id)
    # Ensure at least one diet type exists so diet_options renders, though not needed for baseline
    trepo = DietTypesRepo(); trepo.create(site_id=site_id, name="Gluten", default_select=False)

    year = 2026; week = 6; day_index = 2
    # Seed residents counts for the selected day and mark Alt2 for dep2 to make baseAlt1 != baseAlt2
    from core.weekview.repo import WeekviewRepo
    repo = WeekviewRepo()
    iso_dow = day_index + 1
    repo.set_residents_counts(tenant_id=1, year=year, week=week, department_id=dep1_id, items=[{"day_of_week": iso_dow, "meal": "lunch", "count": 10}])
    repo.set_residents_counts(tenant_id=1, year=year, week=week, department_id=dep2_id, items=[{"day_of_week": iso_dow, "meal": "lunch", "count": 7}])
    _ensure_alt2_for_dep(dep2_id, site_id, year, week, iso_dow)

    client = app_session.test_client()
    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Baseline spans should exist
    assert 'id="kp-base-alt1"' in html
    assert 'id="kp-base-alt2"' in html
    assert 'id="kp-base-total"' in html
    # Expect values equal to fixed counts distributed by alt choice
    # With dep1 Alt1 and dep2 Alt2: alt1=10, alt2=7, total=17
    import re
    m1 = re.search(r'id="kp-base-alt1">(\d+)<', html)
    m2 = re.search(r'id="kp-base-alt2">(\d+)<', html)
    mt = re.search(r'id="kp-base-total"[^>]*>(\d+)<', html)
    assert m1 and m2 and mt
    v1 = int(m1.group(1)); v2 = int(m2.group(1)); vt = int(mt.group(1))
    assert v1 == 10
    assert v2 == 7
    assert vt == v1 + v2
