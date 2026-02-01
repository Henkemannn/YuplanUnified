from sqlalchemy import text

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-alt2-ui','Alt2 UI Site')"))
        conn.execute(text(
            "INSERT OR IGNORE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
            "VALUES ('dept-alt2-ui','site-alt2-ui','Avd UI','fixed', 5)"
        ))
        conn.commit()
    finally:
        conn.close()


def test_admin_edit_alt2_modal_has_day_buttons_and_save(app_session, client_admin):
    _seed_basics()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-alt2-ui"
    r = client_admin.get("/ui/admin/departments/dept-alt2-ui/edit", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Pre-rendered 7 day buttons and save button class
    assert html.count('class="alt2-day js-alt2-day"') == 7
    assert 'class="yp-button yp-button-primary js-alt2-save"' in html
