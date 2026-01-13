import uuid

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_switch_back_to_fixed_clears_schedules(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site and dept
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site F',0)"), {"i": site_id})
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
            "name": "DeptFixed",
            "resident_count": "8",
            "resident_count_mode_choice": "fixed",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='DeptFixed' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # Seed week override (week=2)
    ResidentsScheduleRepo().upsert_items(dep_id, 2, [{"weekday": 1, "meal": "lunch", "count": 9}])
    # Switch back to fixed via edit save
    resp2 = client_admin.post(
        f"/ui/admin/departments/{dep_id}/edit",
        headers=_h("admin"),
        data={
            "name": "DeptFixed",
            "resident_count": "8",
            "resident_count_mode_choice": "fixed",
            "version": "0",
        },
        follow_redirects=False,
    )
    assert resp2.status_code in (301, 302)
    # Verify schedules cleared and mode fixed
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT resident_count_mode FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
            assert (row[0] or '').strip() == 'fixed'
            # No schedule rows remain
            any_row = db.execute(text("SELECT 1 FROM department_residents_schedule WHERE department_id=:d"), {"d": dep_id}).fetchone()
            assert any_row is None
        finally:
            db.close()


def test_clear_week_override_button(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site and dept
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site CW',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create dept variable via forever schedule
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "DeptCW",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "week",
            "selected_week_create": "3",
            "create_day_1_lunch": "9",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='DeptCW' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # Confirm week 3 exists
    sched = ResidentsScheduleRepo().get_week(dep_id, 3)
    assert len(sched) > 0
    # Clear week via modal route
    resp2 = client_admin.post(
        f"/ui/admin/departments/{dep_id}/variation",
        headers=_h("admin"),
        data={
            "mode": "week",
            "selected_week_override": "3",
            "action": "clear_week",
            "return_to": "edit",
        },
        follow_redirects=False,
    )
    assert resp2.status_code in (301, 302)
    # Verify deletion
    sched2 = ResidentsScheduleRepo().get_week(dep_id, 3)
    assert len(sched2) == 0
