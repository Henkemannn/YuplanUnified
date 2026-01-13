import uuid
from sqlalchemy import text

HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_with_departments():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep1 = str(uuid.uuid4())
        dep2 = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,'Site',0)"), {"i": site_id})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,'Avd 1','fixed',5,0)"), {"i": dep1, "s": site_id})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,'Avd 2','fixed',6,0)"), {"i": dep2, "s": site_id})
        db.commit()
        return site_id, dep1, dep2
    finally:
        db.close()


def test_portal_week_shows_picker_when_missing_department(app_session):
    client = app_session.test_client()
    site_id, dep1, dep2 = _seed_site_with_departments()
    year, week = 2026, 8
    r = client.get(f"/ui/portal/week?site_id={site_id}&year={year}&week={week}", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Contains select with both departments
    assert '<select id="portal-department-select"' in html
    assert 'Avd 1' in html and 'Avd 2' in html
    # Save button disabled until chosen
    assert '<button type="submit" class="yp-btn" disabled>' in html


def test_select_department_sets_session_and_enables_choices(app_session):
    client = app_session.test_client()
    site_id, dep1, dep2 = _seed_site_with_departments()
    year, week = 2026, 9
    # POST select department
    form = {"site_id": site_id, "department_id": dep1, "year": str(year), "week": str(week)}
    r_post = client.post("/ui/portal/select-department", data=form, headers=HEADERS_ADMIN, follow_redirects=False)
    assert r_post.status_code in (302, 303)
    # GET portal week should show department name and choices
    r = client.get(f"/ui/portal/week?site_id={site_id}&year={year}&week={week}", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Avdelning: Avd 1' in html
    # Radios visible Mon–Fri (look for name="choice_1" etc.)
    assert 'name="choice_1"' in html and 'name="choice_5"' in html
    # Save button enabled
    assert '<button type="submit" class="yp-btn">Spara menyval</button>' in html
