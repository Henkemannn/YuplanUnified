from tests._auth_site_helpers import login_bound_user
import pytest
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _enable_weekview_feature(client_admin) -> None:
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200


@pytest.fixture
def enable_weekview(client_admin):
    _enable_weekview_feature(client_admin)


pytestmark = pytest.mark.usefixtures("enable_weekview")


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='b308edac-0418-5f28-bc16-994c8220758a'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, tenant_id, name) VALUES ('b308edac-0418-5f28-bc16-994c8220758a', 1, 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='cab28fa2-6fe1-5d68-b273-fd9143994270'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('cab28fa2-6fe1-5d68-b273-fd9143994270', 'b308edac-0418-5f28-bc16-994c8220758a', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def test_kitchen_week_has_shared_menu_modal(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "b308edac-0418-5f28-bc16-994c8220758a"
    login_bound_user(client, site_id=site_id)
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="menuModal"' in html
    assert 'js/menu_modal.js' in html
    assert 'data-action="open-menu-modal"' in html
    assert 'class="menu-icon"' in html
    assert 'js-menu-modal-close' in html
