from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_two_departments_and_diets():
    from core.db import get_session
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000030"
        dep1 = "00000000-0000-0000-0000-000000000031"
        dep2 = "00000000-0000-0000-0000-000000000032"
        # Site
        if not conn.execute(text("SELECT 1 FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone():
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, :name)"), {"sid": site_id, "name": "Kitchen Test Site"})
        # Departments
        if not conn.execute(text("SELECT 1 FROM departments WHERE id=:did"), {"did": dep1}).fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, :name, 'fixed', 12)"), {"did": dep1, "sid": site_id, "name": "Avd One"})
        if not conn.execute(text("SELECT 1 FROM departments WHERE id=:did"), {"did": dep2}).fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, :name, 'fixed', 9)"), {"did": dep2, "sid": site_id, "name": "Avd Two"})
        conn.commit()
    finally:
        conn.close()
    # Diet types and mapping
    from core.admin_repo import DietTypesRepo
    repo = DietTypesRepo()
    timbal_id = repo.create(site_id=site_id, name="Timbal", default_select=False)
    gluten_id = repo.create(site_id=site_id, name="Gluten", default_select=False)
    # Link Timbal -> Dep1, Gluten -> Dep2 via defaults mapping
    conn = get_session()
    try:
        # Ensure defaults table exists and insert links
        conn.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
        conn.execute(text("INSERT OR IGNORE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES (:d1, :timbal, 0)"), {"d1": dep1, "timbal": str(timbal_id)})
        conn.execute(text("INSERT OR IGNORE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES (:d2, :gluten, 0)"), {"d2": dep2, "gluten": str(gluten_id)})
        conn.commit()
    finally:
        conn.close()
    return {
        "site_id": site_id,
        "dep1": dep1,
        "dep2": dep2,
        "timbal_id": timbal_id,
        "gluten_id": gluten_id,
    }


def test_department_scoped_diets_and_residents(app_session):
    client = app_session.test_client()
    ctx = _seed_two_departments_and_diets()
    site_id = ctx["site_id"]
    dep1 = ctx["dep1"]
    dep2 = ctx["dep2"]

    # Request kitchen week for the whole site (both departments)
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    # Dept1 should show Timbal but not Gluten; residents=12
    assert "Avd One" in html
    # Narrow to the section by searching after department name
    idx1 = html.find("Avd One")
    assert idx1 != -1
    seg1 = html[idx1: idx1 + 5000]
    assert "Timbal" in seg1
    assert "Gluten" not in seg1
    assert "12 boende" in seg1

    # Dept2 should show Gluten but not Timbal; residents=9
    assert "Avd Two" in html
    idx2 = html.find("Avd Two")
    assert idx2 != -1
    seg2 = html[idx2: idx2 + 5000]
    assert "Gluten" in seg2
    assert "Timbal" not in seg2
    assert "9 boende" in seg2
