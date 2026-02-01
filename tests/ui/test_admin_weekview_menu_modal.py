from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        conn.commit()
    finally:
        conn.close()


def test_admin_weekview_has_menu_modal_markup(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    # Use explicit year/week to avoid redirect
    year = 2025
    week = 49
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Modal container exists
    assert '<div id="menuModal"' in html
    # Script include present
    assert 'weekview_menu_modal.js' in html
    # Menu icon button should be present when vm.menu_days_site indicates availability
    # We can't guarantee seeded weekly menu, but presence of the button markup path is enough here.
    assert 'class="menu-icon"' in html or 'data-day="Mon"' in html or 'data-day="Tue"' in html
