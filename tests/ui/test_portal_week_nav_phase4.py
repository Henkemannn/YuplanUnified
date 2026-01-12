import uuid
from sqlalchemy import text

HEADERS_PORTAL = {"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}


def _seed_site_dep():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PortalSite"})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',8,0)"), {"i": dep_id, "s": site_id, "n": "Avd Portal"})
        db.commit()
        return site_id, dep_id
    finally:
        db.close()


def test_week_nav_and_jump_controls(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep()
    year, week = 2026, 8
    r = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f"Vecka {week}" in html
    # Prev/next links include correct params
    assert f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year=2026&week=7" in html
    assert f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year=2026&week=9" in html
    # Jump controls exist
    assert 'name="year"' in html and 'name="week"' in html and 'Gå' in html


def test_missing_department_shows_banner_and_disables_save(app_session):
    client = app_session.test_client()
    site_id, _dep_id = _seed_site_dep()
    year, week = 2026, 10
    # Omit department_id on purpose
    r = client.get(f"/ui/portal/week?site_id={site_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Warning banner present
    assert "Ingen avdelning vald" in html
    # Save button disabled
    assert '<button type="submit" class="yp-btn" disabled>' in html
