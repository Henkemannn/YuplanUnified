from tests._auth_site_helpers import login_bound_user

HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_COOK = {"X-User-Role": "cook", "X-Tenant-Id": "1"}


def _seed_site_dep_defaults(app, site_name="TestSite"):
    from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo

    with app.app_context():
        site, _ = SitesRepo().create_site(name=site_name, tenant_id=1)
        department, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name="Avd X",
            resident_count_mode="fixed",
            resident_count_fixed=8,
            notes="Initial note",
        )
        diet_repo = DietTypesRepo()
        diet_ids = {
            name: diet_repo.create(
                site_id=site["id"],
                tenant_id=1,
                name=name,
                semantics="atomic",
            )
            for name in ("Gluten", "Laktos")
        }
        DepartmentsRepo().upsert_department_diet_defaults(
            department["id"],
            0,
            [
                {"diet_type_id": str(diet_ids["Gluten"]), "default_count": 2},
                {"diet_type_id": str(diet_ids["Laktos"]), "default_count": 1},
            ],
        )
    return site["id"], department["id"], diet_ids


def test_admin_settings_get_and_post(app_session):
    client = app_session.test_client()
    site_id, dep_id, diet_ids = _seed_site_dep_defaults(app_session)
    login_bound_user(client, site_id=site_id)

    # GET as admin
    r_get = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN)
    assert r_get.status_code == 200
    html = r_get.get_data(as_text=True)
    assert "Avdelningsinställningar" in html
    assert "Avd X" in html
    assert "Antal boende totalt" in html
    assert "Initial note" in html
    assert "Gluten" in html and "Laktos" in html

    # POST updates: residents 10, Gluten 3, note changed
    form = {
        "residents_base_count": "10",
        "notes": "Uppdaterad faktaruta",
        "diet_type_id[]": [str(diet_ids["Gluten"]), str(diet_ids["Laktos"])],
        "planned_count[]": ["3", "1"],
    }
    r_post = client.post(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN, data=form)
    # Depending on test client settings, POST may return 302 redirect or already-followed 200
    assert r_post.status_code in (200, 302, 303)
    r_get2 = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_ADMIN)
    assert r_get2.status_code == 200
    html2 = r_get2.get_data(as_text=True)
    assert "value=\"10\"" in html2
    assert "Uppdaterad faktaruta" in html2
    # Updated planned_count should reflect 3 for Gluten
    assert "Gluten" in html2 and "value=\"3\"" in html2

    # RBAC: cook should be allowed (SAFE_UI_ROLES), but a role outside should be blocked
    # Use a non-admin role to verify access denied
    r_forbidden = client.get(f"/ui/admin/departments/{dep_id}/settings", headers={"X-User-Role": "user", "X-Tenant-Id": "1"})
    assert r_forbidden.status_code in (302, 403, 401)


def test_admin_settings_integration_with_weekview_report(app_session):
    client = app_session.test_client()
    site_id, dep_id, _diet_ids = _seed_site_dep_defaults(app_session)
    login_bound_user(client, site_id=site_id)

    # After changing defaults, weekview report should reflect planned counts via debiterbar logic when marked.
    # Simple check: CSV header present and contains department name; we won't mark here.
    year, week = 2025, 12
    # ensure site context
    resp_csv = client.get(f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}")
    assert resp_csv.status_code == 200
    body = resp_csv.data.decode("utf-8")
    assert "site,department,year,week,meal,residents_total,debiterbar_specialkost,normal_count" in body.splitlines()[0]
    # Department name appears somewhere in rows
    assert any("Avd X" in ln for ln in body.splitlines()[1:])
