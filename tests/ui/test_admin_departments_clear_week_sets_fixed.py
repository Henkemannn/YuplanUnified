import uuid

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_clear_week_makes_mode_fixed_when_no_schedules_remain(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site CF',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create fixed dept
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "DeptCF",
            "resident_count": "8",
            "resident_count_mode_choice": "fixed",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve dept id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='DeptCF' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # Add a week override
    ResidentsScheduleRepo().upsert_items(dep_id, 5, [{"weekday": 1, "meal": "lunch", "count": 9}])
    # Clear week via modal endpoint
    resp2 = client_admin.post(
        f"/ui/admin/departments/{dep_id}/variation",
        headers=_h("admin"),
        data={
            "mode": "week",
            "selected_week_override": "5",
            "action": "clear_week",
            "return_to": "edit",
        },
        follow_redirects=False,
    )
    assert resp2.status_code in (301, 302)
    # DB should switch mode back to fixed
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT resident_count_mode FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
            assert (row[0] or '').strip() == 'fixed'
        finally:
            db.close()
    # Edit view should render fixed radio checked
    resp3 = client_admin.get(f"/ui/admin/departments/{dep_id}/edit", headers=_h("admin"))
    html = resp3.get_data(as_text=True)
    assert 'name="resident_count_mode_choice" value="fixed" checked' in html or 'value="fixed" checked' in html
