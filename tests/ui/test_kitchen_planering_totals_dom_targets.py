from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, name) VALUES (:id, :name)"),
            {"id": "00000000-0000-0000-0000-000000000000", "name": "Test Site"},
        )
        conn.commit()
    finally:
        conn.close()


def test_planering_totals_dom_targets_exist(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    # Seed minimal department and diet so baselines are nonzero
    from core.admin_repo import DepartmentsRepo, DietTypesRepo
    drepo = DepartmentsRepo()
    dep, _v = drepo.create_department(site_id, "Avd 1", "fixed", 5)
    trepo = DietTypesRepo()
    dt_id = trepo.create(site_id=site_id, name="Glutenfri", default_select=False)
    ver = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], ver, [{"diet_type_id": str(dt_id), "default_count": 2}])

    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&mode=normal", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'data-result-normal="alt1"' in html
    assert 'data-result-normal="alt2"' in html
    # Baselines may be exposed via id hooks for backward compatibility
    assert 'id="kp-base-alt1"' in html
    assert 'id="kp-base-alt2"' in html
