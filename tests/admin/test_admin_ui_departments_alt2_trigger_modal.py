from sqlalchemy import text

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-alt2-2','Alt2 Site 2')"))
        conn.execute(text(
            "INSERT OR IGNORE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
            "VALUES ('dept-alt2-2','site-alt2-2','Avd Beta','fixed', 7)"
        ))
        conn.commit()
    finally:
        conn.close()


def test_admin_edit_contains_alt2_trigger_modal_and_script(app_session, client_admin):
    _seed_basics()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-alt2-2"
    r = client_admin.get("/ui/admin/departments/dept-alt2-2/edit", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'class="yp-button yp-button-secondary js-open-alt2"' in html
    assert 'id="alt2Modal"' in html
    assert 'js/admin_alt2.js' in html
