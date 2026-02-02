from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal_site_dep():
    from core.db import get_session
    conn = get_session()
    try:
        site_id = 'site-icons-1'
        dep_id = 'dep-icons-1'
        row = conn.execute(text("SELECT 1 FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if not row:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:id, 'Site Icons')"), {"id": site_id})
        row = conn.execute(text("SELECT 1 FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
        if not row:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES (:id, :sid, 'Avd Icons', 'fixed', 3, 0)"), {"id": dep_id, "sid": site_id})
        conn.commit()
        return site_id, dep_id
    finally:
        conn.close()


def test_weekview_header_icons(app_session):
    client = app_session.test_client()
    site_id, _ = _seed_minimal_site_dep()
    year, week = 2026, 8
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode('utf-8')
    # Assert icons are present in header row with aria-hidden
    assert '<span class="meal-icon" aria-hidden="true">🍽️</span>' in html
    assert '<span class="meal-icon" aria-hidden="true">🌙</span>' in html
    # Screen-reader text present
    assert '<span class="yp-sr-only">Lunch</span>' in html
    assert '<span class="yp-sr-only">Kväll</span>' in html
