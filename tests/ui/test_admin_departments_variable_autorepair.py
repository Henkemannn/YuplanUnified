import uuid

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_edit_view_forces_variable_mode_and_repairs_mode(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site R',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create department with fixed mode
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "DeptRepair",
            "resident_count": "5",
            "resident_count_mode_choice": "fixed",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Get dept id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='DeptRepair' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # Seed a week schedule row while mode remains fixed
    ResidentsScheduleRepo().upsert_items(dep_id, 1, [{"weekday": 1, "meal": "lunch", "count": 9}])
    # GET edit page should show variable radio checked
    resp2 = client_admin.get(f"/ui/admin/departments/{dep_id}/edit", headers=_h("admin"))
    assert resp2.status_code == 200
    import re
    html = resp2.get_data(as_text=True)
    assert re.search(r'<input[^>]*name="resident_count_mode_choice"[^>]*value="variable"[^>]*checked', html)
    # DB should be auto-repaired to variable mode
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT resident_count_mode FROM departments WHERE id=:id AND site_id=:s"), {"id": dep_id, "s": site_id}).fetchone()
            assert row is not None
            assert (row[0] or '').strip() == 'variable'
        finally:
            db.close()
