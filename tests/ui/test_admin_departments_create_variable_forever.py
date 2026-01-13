import uuid
from datetime import date as _date

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_create_department_variable_forever_fallback(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site C',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create department with variable default schedule (tills vidare)
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "ForeverDept",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "forever",
            # Monday defaults
            "create_day_1_lunch": "11",
            "create_day_1_dinner": "4",
            # Wednesday
            "create_day_3_lunch": "9",
            "create_day_3_dinner": "2",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve dept id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='ForeverDept' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # Verify default schedule persisted
    forever = ResidentsScheduleRepo().get_forever(dep_id)
    idx_f = {(int(it['weekday']), str(it['meal'])): int(it['count']) for it in forever}
    assert idx_f.get((1,'lunch')) == 11
    assert idx_f.get((1,'dinner')) == 4
    assert idx_f.get((3,'lunch')) == 9
    assert idx_f.get((3,'dinner')) == 2
    # Verify detail view falls back to default when no week-specific schedule exists
    resp_detail = client_admin.get(f"/ui/admin/departments/{dep_id}/detail", headers=_h("admin"))
    assert resp_detail.status_code == 200
    html = resp_detail.get_data(as_text=True)
    # Expect numbers from forever schedule rendered in weekly table
    assert "11" in html
    assert "4" in html
    assert "9" in html
    assert "2" in html
