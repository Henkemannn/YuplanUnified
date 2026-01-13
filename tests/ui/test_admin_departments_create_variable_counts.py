import uuid
from datetime import date as _date

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_create_department_fixed_mode_persists_fixed_count(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site A',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Post create with fixed mode
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "FixedDept",
            "resident_count": "23",
            "resident_count_mode_choice": "fixed",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Verify DB saved fixed count
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT resident_count_fixed, resident_count_mode FROM departments WHERE name='FixedDept' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            assert int(row[0]) == 23
            # mode may be 'fixed'
            assert (row[1] or 'fixed') in ('fixed','manual',None)
        finally:
            db.close()


def test_create_department_variable_mode_persists_schedule(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site B',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Choose a week
    iso = _date.today().isocalendar()
    week = iso[1]
    # Create department with variable counts for two days
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "VarDept",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "week",
            "selected_week_create": str(week),
            "selected_year_create": str(iso[0]),
            # Monday
            "create_day_1_lunch": "10",
            "create_day_1_dinner": "5",
            # Tuesday
            "create_day_2_lunch": "7",
            "create_day_2_dinner": "3",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve dept id and verify schedule rows
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='VarDept' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    sched = ResidentsScheduleRepo().get_week(dep_id, week)
    # Make an index for assertions
    idx = {(int(it['weekday']), str(it['meal'])): int(it['count']) for it in sched}
    assert idx.get((1,'lunch')) == 10
    assert idx.get((1,'dinner')) == 5
    assert idx.get((2,'lunch')) == 7
    assert idx.get((2,'dinner')) == 3
