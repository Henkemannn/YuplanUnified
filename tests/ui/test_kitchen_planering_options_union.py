import uuid

from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_union():
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
    site, _ = SitesRepo().create_site("Plan Site", tenant_id=1)
    site_id = site["id"]
    # Create three departments
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id, "Avd A", "fixed", 12)
    depB, _ = drepo.create_department(site_id, "Avd B", "fixed", 10)
    depC, _ = drepo.create_department(site_id, "Avd C", "fixed", 11)
    # Use the site's provisioned canonical types.
    trepo = DietTypesRepo()
    types = {row["name"]: row for row in trepo.list_all(site_id=site_id)}
    dt_laktos = int(types["Laktosfri"]["id"])
    dt_gluten = int(types["Glutenfri"]["id"])
    # Upsert defaults per department
    vA = drepo.get_version(depA["id"]) or 0
    vB = drepo.get_version(depB["id"]) or 0
    vC = drepo.get_version(depC["id"]) or 0
    drepo.upsert_department_diet_defaults(depA["id"], vA, [
        {"diet_type_id": str(dt_laktos), "default_count": 3},
        {"diet_type_id": str(dt_gluten), "default_count": 1},
    ])
    drepo.upsert_department_diet_defaults(depB["id"], vB, [
        {"diet_type_id": str(dt_laktos), "default_count": 2},
        {"diet_type_id": str(dt_gluten), "default_count": 0},
    ])
    drepo.upsert_department_diet_defaults(depC["id"], vC, [
        {"diet_type_id": str(dt_laktos), "default_count": 4},
        {"diet_type_id": str(dt_gluten), "default_count": 2},
    ])
    return {
        "site_id": site_id,
        "deps": (depA, depB, depC),
        "diet_ids": {"laktos": dt_laktos, "gluten": dt_gluten},
    }


def test_options_union_render(app_session):
    client = app_session.test_client()
    seeded = _seed_union()
    site_id = seeded["site_id"]
    # Select a day + meal to show checklist
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Expect union diet names in chips
    assert "Laktos" in html
    assert "Glutenfri" in html
