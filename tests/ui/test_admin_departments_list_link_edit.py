import uuid

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_department_name_links_to_edit_page(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    # Seed site and department
    site_id = str(uuid.uuid4())
    dept_id = None
    with app_session.app_context():
      db = get_session()
      try:
        db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site L',0)"), {"i": site_id})
        db.execute(text("INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES(:d,:s,'Dept L','fixed',3,0)"), {"d": str(uuid.uuid4()), "s": site_id})
        row = db.execute(text("SELECT id FROM departments WHERE name='Dept L' AND site_id=:s"), {"s": site_id}).fetchone()
        assert row is not None
        dept_id = str(row[0])
        db.commit()
      finally:
        db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # GET departments list
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Expect anchor href to canonical edit route
    expected_path = f"/ui/admin/departments/{dept_id}/edit"
    assert expected_path in html
