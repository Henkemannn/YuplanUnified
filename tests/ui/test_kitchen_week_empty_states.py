from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_only():
    from core.db import get_session
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000010"
        site = conn.execute(text("SELECT id FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, :name)"), {"sid": site_id, "name": "Empty Site"})
        conn.commit()
    finally:
        conn.close()


def _seed_site_with_department_without_diets():
    from core.db import get_session
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000020"
        dep_id = "00000000-0000-0000-0000-000000000021"
        site = conn.execute(text("SELECT id FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, :name)"), {"sid": site_id, "name": "Site With Deps"})
        dep = conn.execute(text("SELECT id FROM departments WHERE id=:did"), {"did": dep_id}).fetchone()
        if not dep:
            conn.execute(
                text(
                    "INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, :name, 'fixed', 3)"
                ),
                {"did": dep_id, "sid": site_id, "name": "Avd Beta"},
            )
        conn.commit()
    finally:
        conn.close()


def test_empty_state_no_departments(app_session):
    client = app_session.test_client()
    _seed_site_only()
    site_id = "00000000-0000-0000-0000-000000000010"
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "<!DOCTYPE html" in html and html.count("<!DOCTYPE html") == 1
    assert "Inga avdelningar" in html
    assert "/static/js/kitchen_week.js" in html


def test_empty_state_no_diets(app_session):
    client = app_session.test_client()
    _seed_site_with_department_without_diets()
    site_id = "00000000-0000-0000-0000-000000000020"
    dep_id = "00000000-0000-0000-0000-000000000021"
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}&department_id={dep_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "<!DOCTYPE html" in html and html.count("<!DOCTYPE html") == 1
    assert "Inga specialkoster" in html
    assert "/static/js/kitchen_week.js" in html
