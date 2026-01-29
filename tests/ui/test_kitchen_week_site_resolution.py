from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_departments(site_id: str):
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:id, 'Accept Site A')"), {"id": site_id})
        depA = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-00000000AA01'"))
        if not depA.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-00000000AA01', :sid, 'Avd One', 'fixed', 4)"), {"sid": site_id})
        depB = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-00000000AA02'"))
        if not depB.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-00000000AA02', :sid, 'Avd Two', 'fixed', 6)"), {"sid": site_id})
        conn.commit()
    finally:
        conn.close()


def test_kitchen_week_site_resolution_uses_session_site(app_session):
    client = app_session.test_client()
    site_id = "11111111-1111-1111-1111-111111111111"
    _seed_site_and_departments(site_id)
    # Set session site_id
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["site_lock"] = False  # ensure it works even when not locked
    rv = client.get("/ui/kitchen/week", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Hidden input should carry non-empty site_id
    assert f'name="site_id" value="{site_id}"' in html
    # Both departments should be present
    assert "Avd One" in html
    assert "Avd Two" in html
    # No DEBUG strings should remain
    assert "DEBUG:" not in html
