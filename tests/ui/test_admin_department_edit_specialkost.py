"""
Verify diet types (specialkost) appear on department edit and can be saved as defaults.
- Seed tenant/site, one diet type, one department
- GET edit form shows the diet type
- POST save defaults, reload shows saved count
"""
import uuid
from sqlalchemy import text


def _h(role: str):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_edit_department_shows_diet_types_and_saves_defaults(app_session, client_admin):
    app = app_session
    site_id = f"site-{uuid.uuid4()}"
    dept_id = f"dept-{uuid.uuid4()}"

    # Seed: site, department, and one tenant-scoped diet type
    from core.db import get_session, create_all
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "Site A"})
            db.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES (:id, :sid, :name, 'fixed', 10, 0)"), {"id": dept_id, "sid": site_id, "name": "Dept A"})
            # Insert one site-scoped diet type via repo to satisfy legacy tenant_id constraints
            from core.admin_repo import DietTypesRepo
            DietTypesRepo().create(site_id=site_id, name="Laktosfri", default_select=False)
            db.commit()
        finally:
            db.close()

    # Set active site in session
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    # GET edit form: shows diet type
    r_get = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    assert r_get.status_code == 200
    html = r_get.data.decode("utf-8")
    assert "Specialkost" in html
    assert "Laktosfri" in html

    # POST save defaults (set 3 for Laktosfri). Version is 0 from seed.
    r_post = client_admin.post(
        f"/ui/admin/departments/{dept_id}/edit/diets",
        headers=_h("admin"),
        data={
            "version": "0",
            "diet_default_1": "3",
        },
        follow_redirects=True,
    )
    assert r_post.status_code == 200

    # Reload and assert persisted value visible
    r_get2 = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    assert r_get2.status_code == 200
    html2 = r_get2.data.decode("utf-8")
    # Look for the input reflecting saved value 3
    assert 'name="diet_default_1"' in html2 and 'value="3"' in html2
