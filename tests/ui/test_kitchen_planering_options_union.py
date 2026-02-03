from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_union(site_id: str):
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
    # Create site
    srepo = SitesRepo()
    srepo.create_site("Plan Site")
    # Create three departments
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id, "Avd A", "fixed", 12)
    depB, _ = drepo.create_department(site_id, "Avd B", "fixed", 10)
    depC, _ = drepo.create_department(site_id, "Avd C", "fixed", 11)
    # Create diet types (site-scoped)
    trepo = DietTypesRepo()
    dt_laktos = trepo.create(site_id=site_id, name="Laktos", default_select=False)
    dt_gluten = trepo.create(site_id=site_id, name="Glutenfri", default_select=False)
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
    return {"deps": (depA, depB, depC), "diet_ids": {"laktos": dt_laktos, "gluten": dt_gluten}}


def test_options_union_render(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    _seed_union(site_id)
    # Select a day + meal to show checklist
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Expect union totals in options (Laktos=3+2+4=9, Glutenfri=1+0+2=3)
    assert "Laktos" in html and "totalt 9" in html
    assert "Glutenfri" in html and "totalt 3" in html
