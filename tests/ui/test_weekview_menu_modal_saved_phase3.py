import json
from sqlalchemy import text


def test_weekview_shows_menu_icon_after_save(client_admin):
    app = client_admin.application
    from core.db import get_session
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER, notes TEXT)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-x','Varberg',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version,notes) VALUES('dep-x','site-x','Avd X','fixed',0,0,'')"))
            db.commit()
        finally:
            db.close()
    # Build weeks json with Tuesday lunch Alt1 non-empty for week 8
    weeks = {
        8: {
            "days": {
                2: {
                    "lunch": {"alt1_text": "Pasta", "alt2_text": "", "dessert": ""},
                    "dinner": {"alt1_text": "", "alt2_text": "", "dessert": ""},
                }
            }
        }
    }
    year = __import__("datetime").date.today().isocalendar()[0]
    # Save into week 8
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tok"
        sess["site_id"] = "site-x"
    resp_save = client_admin.post(
        "/ui/admin/menu-import/preview/save",
        data={
            "year": str(year),
            "weeks_json": json.dumps(weeks),
            "csrf_token": "tok",
        },
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1", "X-Site-Id": "site-x", "X-CSRF-Token": "tok"},
    )
    assert resp_save.status_code in (200, 302)

    # Render weekview for week 8
    resp = client_admin.get(
        "/ui/weekview",
        query_string={"site_id": "site-x", "department_id": "", "year": year, "week": 8},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1", "X-Site-Id": "site-x"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Presence: 📋 trigger present for Tuesday header (data-day="2")
    assert 'class="ua-icon-btn js-open-modal js-open-menu-modal"' in html
    assert 'data-day="2"' in html
    # Absence: Monday header should not show trigger button (no saved menu)
    assert 'data-day="1">📋' not in html
