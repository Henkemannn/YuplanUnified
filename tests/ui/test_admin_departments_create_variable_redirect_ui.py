import uuid
from datetime import date as _date

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_create_department_variable_week_redirect_shows_values(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site V',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    iso = _date.today().isocalendar()
    week = iso[1]
    # Create with variable week scope and some values
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "VarDeptUI",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "week",
            "selected_week_create": str(week),
            "selected_year_create": str(iso[0]),
            "create_day_1_lunch": "12",
            "create_day_1_dinner": "6",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # The edit page should show at least one of the entered numbers
    assert "12" in html or "6" in html


def test_create_department_variable_forever_redirect_shows_values(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    # Seed site
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'Site VF',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    # Bind session site
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create with variable forever scope and some values
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "ForeverDeptUI",
            "resident_count": "0",
            "resident_count_mode_choice": "variable",
            "variation_scope_create": "forever",
            "create_day_2_lunch": "9",
            "create_day_2_dinner": "4",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "9" in html or "4" in html
