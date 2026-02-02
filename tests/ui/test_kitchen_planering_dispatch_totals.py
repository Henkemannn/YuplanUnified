HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_dispatch(site_id: str):
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
    srepo = SitesRepo()
    srepo.create_site("Plan Site")
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id, "Avd A", "fixed", 12)
    depB, _ = drepo.create_department(site_id, "Avd B", "fixed", 10)
    depC, _ = drepo.create_department(site_id, "Avd C", "fixed", 11)
    trepo = DietTypesRepo()
    dt_laktos = trepo.create(site_id=site_id, name="Laktos", default_select=False)
    vA = drepo.get_version(depA["id"]) or 0
    vB = drepo.get_version(depB["id"]) or 0
    vC = drepo.get_version(depC["id"]) or 0
    drepo.upsert_department_diet_defaults(depA["id"], vA, [{"diet_type_id": str(dt_laktos), "default_count": 3}])
    drepo.upsert_department_diet_defaults(depB["id"], vB, [{"diet_type_id": str(dt_laktos), "default_count": 2}])
    drepo.upsert_department_diet_defaults(depC["id"], vC, [{"diet_type_id": str(dt_laktos), "default_count": 4}])
    return {"deps": (depA, depB, depC), "diet_id": dt_laktos}


def test_dispatch_totals_selected_diet(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    seeded = _seed_dispatch(site_id)
    dt_id = seeded["diet_id"]
    # Select day+meal and pass selected_diets=laktos
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&selected_diets={dt_id}&show_results=1", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Summary: residents total = 12+10+11=33; special_to_adapt_total = 9; normal_remaining = 24
    assert ">33<" in html or ">33</div>" in html
    assert ">9<" in html
    assert ">24<" in html
    # Adaptation list includes per-department rows
    assert "Avd A" in html and ">3<" in html
    assert "Avd B" in html and ">2<" in html
    assert "Avd C" in html and ">4<" in html
