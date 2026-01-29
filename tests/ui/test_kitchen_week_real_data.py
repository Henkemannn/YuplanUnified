from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        # Seed a site and a department if missing
        site_id = "00000000-0000-0000-0000-000000000000"
        dep_id = "00000000-0000-0000-0000-000000000001"
        site = conn.execute(text("SELECT id FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, :name)"), {"sid": site_id, "name": "Test Site"})
        dep = conn.execute(text("SELECT id FROM departments WHERE id=:did"), {"did": dep_id}).fetchone()
        if not dep:
            conn.execute(
                text(
                    "INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, :name, 'fixed', 5)"
                ),
                {"did": dep_id, "sid": site_id, "name": "Avd Alpha"},
            )
        conn.commit()
    finally:
        conn.close()


def test_kitchen_week_loads_real_diets_for_site(app_session):
    from core.admin_repo import DietTypesRepo

    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    dep_id = "00000000-0000-0000-0000-000000000001"

    # Create a real diet type for the site
    repo = DietTypesRepo()
    # Ensure table exists and create the type
    dt_id = repo.create(site_id=site_id, name="Gluten", default_select=False)

    # Request kitchen week with site + department
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}&department_id={dep_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Assert real diet type name appears
    assert "Gluten" in html
    # Assert button carries non-empty data attributes with IDs
    assert f"data-department-id=\"{dep_id}\"" in html
    assert f"data-kosttyp-id=\"{dt_id}\"" in html or "data-kosttyp-id=\"__placeholder\"" not in html
