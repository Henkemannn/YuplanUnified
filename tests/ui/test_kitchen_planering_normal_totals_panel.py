HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_planering_normal_totals_panel_ids_present(app_session):
    from core.admin_repo import SitesRepo, DietTypesRepo, DepartmentsRepo
    srepo = SitesRepo(); srepo.create_site("Totals Site")
    site_id = srepo.list_sites()[0]["id"]
    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id, "Avd X", "fixed", 8)
    trepo = DietTypesRepo()
    # Create one diet type and a default count so diet_options exists
    diet_id = trepo.create(site_id=site_id, name="Gluten", default_select=False)
    v = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], v, [{"diet_type_id": str(diet_id), "default_count": 3}])

    client = app_session.test_client()
    year = 2026; week = 6; day_index = 2
    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Panel IDs should be present in normal lunch mode
    assert 'id="kp-total-alt1"' in html
    assert 'id="kp-total-alt2"' in html
    assert 'id="kp-total-sum"' in html
