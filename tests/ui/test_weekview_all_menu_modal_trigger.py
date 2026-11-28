from tests._auth_site_helpers import login_bound_user
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        # Minimal site and one department so weekview_all renders department cards
        site = conn.execute(text("SELECT id FROM sites WHERE id='dabd61e2-9058-509d-8b28-19371e92e299'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, tenant_id, name) VALUES ('dabd61e2-9058-509d-8b28-19371e92e299', 1, 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='8bd0abb1-36c7-5839-a420-c04be26ad004'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('8bd0abb1-36c7-5839-a420-c04be26ad004', 'dabd61e2-9058-509d-8b28-19371e92e299', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def test_weekview_all_has_menu_modal_trigger(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "dabd61e2-9058-509d-8b28-19371e92e299"
    login_bound_user(client, site_id=site_id)
    year = 2026
    week = 8
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Modal container exists
    assert '<div id="menuModal"' in html
    # Shared script include present
    assert 'js/menu_modal.js' in html
    # Trigger markup present
    assert 'data-action="open-menu-modal"' in html
    assert 'class="menu-icon"' in html
    # Dataset keys present
    assert 'data-day-index="' in html and 'data-year="' in html and 'data-week="' in html
