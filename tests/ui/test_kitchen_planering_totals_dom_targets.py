import uuid

from sqlalchemy import text


def _seed_basics():
    from core.db import get_session

    site_id = str(uuid.uuid4())
    conn = get_session()
    try:
        conn.execute(
            text(
                "INSERT INTO sites (id, tenant_id, name) "
                "VALUES (:id, 1, :name)"
            ),
            {"id": site_id, "name": f"Planera totals {uuid.uuid4()}"},
        )
        conn.commit()
    finally:
        conn.close()
    return site_id


def test_planering_totals_dom_targets_exist(app_session):
    client = app_session.test_client()
    site_id = _seed_basics()
    # Seed minimal department and diet so baselines are nonzero
    from core.admin_repo import DepartmentsRepo, DietTypesRepo

    drepo = DepartmentsRepo()
    dep, _v = drepo.create_department(site_id, "Avd 1", "fixed", 5)
    trepo = DietTypesRepo()
    dt_id = trepo.create(
        site_id=site_id,
        tenant_id=1,
        name=f"Glutenfri-{uuid.uuid4().hex}",
        default_select=False,
    )
    assert dep["site_id"] == site_id
    ver = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], ver, [{"diet_type_id": str(dt_id), "default_count": 2}])

    from tests._auth_site_helpers import login_bound_user

    login_bound_user(client, site_id=site_id)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&mode=normal")
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'data-result-normal="alt1"' in html
    assert 'data-result-normal="alt2"' in html
    # Baselines may be exposed via id hooks for backward compatibility
    assert 'id="kp-base-alt1"' in html
    assert 'id="kp-base-alt2"' in html
