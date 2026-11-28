from tests._auth_site_helpers import login_bound_user
import pytest
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
SITE_ID = "7f76ecfc-1a7c-5918-b340-fdfa23a9f9f0"
DEPARTMENT_ID = "665401bb-d68a-50dd-9b76-8670e8adbd4d"


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
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, tenant_id, name) VALUES (:id, 1, :name)"),
            {"id": SITE_ID, "name": "Test Site"},
        )
        conn.execute(
            text(
                "INSERT OR IGNORE INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) "
                "VALUES (:id, :site_id, :name, :mode, :fixed)"
            ),
            {
                "id": DEPARTMENT_ID,
                "site_id": SITE_ID,
                "name": "Avd Alpha",
                "mode": "fixed",
                "fixed": 5,
            },
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    "path",
    [
        f"/ui/kitchen/planering?site_id={SITE_ID}",
        f"/ui/kitchen/week?site_id={SITE_ID}",
        pytest.param(
            f"/ui/weekview?site_id={SITE_ID}&year=2026&week=8",
            id="/ui/weekview?site_id=00000000-0000-0000-0000-000000000000&year=2026&week=8",
        ),
    ],
)
def test_menu_modal_contract(app_session, path):
    client = app_session.test_client()
    _seed_basics()
    login_bound_user(client, site_id=SITE_ID)
    if path.startswith("/ui/kitchen/week"):
        with client.session_transaction() as sess:
            sess["site_id"] = SITE_ID
    rv = client.get(path, headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert html.count('id="menuModal"') == 1
    assert 'data-action="open-menu-modal"' in html
    assert 'js/menu_modal.js' in html
