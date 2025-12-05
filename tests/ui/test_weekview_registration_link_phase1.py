from datetime import date as _date
from sqlalchemy import text


HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'")) .fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'")) .fetchone()
        if not dep:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def test_weekview_shows_registration_link_get_only(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    dep_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 45

    # Monday ISO date for assertions
    mon = _date.fromisocalendar(year, week, 1).isoformat()

    resp = client.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")

    # Expect at least one lunch registration link for the week (Mon)
    expected_href = f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={mon}&meal=lunch"
    assert expected_href in body

    # Link is simple anchor navigation (GET); no client-side override attribute
    assert 'data-method="post"' not in body.lower()
