from sqlalchemy import text
import pytest

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
SITE_ID = "00000000-0000-0000-0000-000000000000"
DEPARTMENT_ID = "00000000-0000-0000-0000-000000000001"


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, name) VALUES (:id, :name)"),
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
        f"/ui/weekview?site_id={SITE_ID}&year=2026&week=8",
    ],
)
def test_menu_modal_contract(app_session, path):
    client = app_session.test_client()
    _seed_basics()
    rv = client.get(path, headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert html.count('id="menuModal"') == 1
    assert 'data-action="open-menu-modal"' in html
    assert 'js/menu_modal.js' in html
