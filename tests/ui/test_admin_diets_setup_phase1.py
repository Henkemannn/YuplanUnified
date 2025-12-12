import uuid


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_admin_diets_page_renders_and_create_type(client_admin):
    app = client_admin.application
    from core.db import create_all, get_session
    from sqlalchemy import text
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Seed a site
            site_id = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Diet Admin Site"})
            db.commit()
        finally:
            db.close()

    # GET page
    r = client_admin.get(f"/ui/admin/diets?site_id={site_id}", headers=_h("admin"))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Specialkosttyper" in html

    # POST create a diet type
    resp = client_admin.post(f"/ui/admin/diets/create?site_id={site_id}", data={"name": "Gluten"}, headers=_h("admin"), follow_redirects=True)
    assert resp.status_code == 200
    assert "Gluten" in resp.get_data(as_text=True)


def test_admin_diets_defaults_save_and_list(client_admin):
    app = client_admin.application
    from core.db import create_all, get_session
    from sqlalchemy import text
    with app.app_context():
        create_all()
        db = get_session()
        try:
            site_id = str(uuid.uuid4())
            dep_id = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Diet Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd 1"})
            db.commit()
        finally:
            db.close()

    # Create one diet type first
    resp = client_admin.post(f"/ui/admin/diets/create?site_id={site_id}", data={"name": "Laktos"}, headers=_h("admin"), follow_redirects=True)
    assert resp.status_code == 200

    # Find the diet type id from repo
    from core.admin_repo import DietTypesRepo, DietDefaultsRepo
    dtypes = DietTypesRepo().list_all(tenant_id=1)
    assert any(dt["name"] == "Laktos" for dt in dtypes)
    dt_id = next(dt["id"] for dt in dtypes if dt["name"] == "Laktos")

    # Save default count = 2 for the department
    resp2 = client_admin.post(
        "/ui/admin/diets/defaults/save",
        data={
            "department_id": dep_id,
            "diet_type_id": str(dt_id),
            "default_count": "2",
        },
        headers=_h("admin"),
        follow_redirects=True,
    )
    assert resp2.status_code == 200

    # Verify via repo
    rows = DietDefaultsRepo().list_for_department(dep_id)
    found = next((r for r in rows if str(r["diet_type_id"]) == str(dt_id)), None)
    assert found is not None
    assert int(found["default_count"]) == 2
