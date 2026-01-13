import uuid
from datetime import date as _date

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_edit_page_shows_variable_and_default_scope_when_forever_exists(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    from core.residents_schedule_repo import ResidentsScheduleRepo
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site S',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create department with variable default schedule
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "DeptS",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "forever",
            "create_day_1_lunch": "8",
            "create_day_1_dinner": "4",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # Resolve department id
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE name='DeptS' AND site_id=:s"), {"s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
        finally:
            db.close()
    # GET edit page
    resp2 = client_admin.get(f"/ui/admin/departments/{dep_id}/edit", headers=_h("admin"))
    assert resp2.status_code == 200
    import re
    html = resp2.get_data(as_text=True)
    # Variable mode radio should be checked
    assert re.search(r'<input[^>]*name="resident_count_mode_choice"[^>]*value="variable"[^>]*checked', html)
    # Edit modal scope should show forever checked and week selector hidden/disabled
    assert 'name="mode" value="forever" checked' in html
    # week selector span should have is-hidden or select disabled
    assert 'js-week-selector' in html
