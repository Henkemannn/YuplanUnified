import uuid
import pytest

from core.db import get_session
from sqlalchemy import text

def test_edit_form_shows_specialkost_heading(client_admin):
    # Create a department
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.execute(text("INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) VALUES (:id, 1, 'Test', 5, 'fixed', 0)"), {"id": dep_id})
        db.commit()
    finally:
        db.close()
    r = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Specialkost (antal på avdelningen)" in html

def test_edit_post_saves_default_and_reads_back(client_admin):
    # Create a department and one diet type
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        # Ensure tables exist in ephemeral sqlite used by tests
        from core.db import create_all
        create_all()
        db.execute(text("INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) VALUES (:id, 1, 'Test', 5, 'fixed', 0)"), {"id": dep_id})
        try:
            db.execute(text("INSERT INTO diet_types (id, tenant_id, name, default_select) VALUES (1, 1, 'Laktos', 0)"))
        except Exception:
            pytest.skip("Diet types table not available")
        db.commit()
    finally:
        db.close()
    # GET to fetch version
    r0 = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r0.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r0.status_code == 200
    # POST with one default
    r1 = client_admin.post(f"/ui/admin/departments/{dep_id}/edit/diets", data={
        "version": "0",
        "diet_default_1": "3",
    })
    assert r1.status_code in (302, 303)
    # Verify via repo
    from core.admin_repo import DietDefaultsRepo
    items = DietDefaultsRepo().list_for_department(dep_id)
    found = {int(it["diet_type_id"]): int(it.get("default_count", 0)) for it in items}
    assert found.get(1) == 3
