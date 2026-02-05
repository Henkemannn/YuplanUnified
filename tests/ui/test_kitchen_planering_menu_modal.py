from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        # Robust insert: avoid collisions on unique name or id
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, name) VALUES (:id, :name)"),
            {"id": "00000000-0000-0000-0000-000000000000", "name": "Test Site"},
        )
        conn.commit()
    finally:
        conn.close()


def test_planering_has_shared_menu_modal(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="menuModal"' in html
    assert 'js/menu_modal.js' in html
    assert 'class="kp-button js-open-menu-modal"' in html
