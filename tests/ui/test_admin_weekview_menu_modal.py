from tests._auth_site_helpers import login_bound_user
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='891bbe11-9337-5276-8f73-d980bf688f69'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, tenant_id, name) VALUES ('891bbe11-9337-5276-8f73-d980bf688f69', 1, 'Test Site')"))
        conn.commit()
    finally:
        conn.close()


def test_admin_weekview_has_menu_modal_markup(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "891bbe11-9337-5276-8f73-d980bf688f69"
    login_bound_user(client, site_id=site_id)
    # Use explicit year/week to avoid redirect
    year = 2025
    week = 49
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Modal container exists
    assert '<div id="menuModal"' in html
    # Shared script include present
    assert 'js/menu_modal.js' in html
    # Icon presence depends on seeded weekly menu; modal container+script are sufficient for M1.1
