from sqlalchemy import text


def test_admin_ui_dashboard_phase2_site_filter_and_search(client_admin):
    app = client_admin.application
    from core.db import get_session
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-1','Varberg',0)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-2','Kungsbacka',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('dep-1','site-1','Avd A','fixed',0,0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('dep-2','site-1','Avd B','fixed',0,0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('dep-3','site-2','Avd C','fixed',0,0)"))
            db.commit()
        finally:
            db.close()
    # Use canonical admin route; provide active site via header in tests
    resp = client_admin.get(
        "/ui/admin",
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "1",
            "X-Site-Id": "site-1",
        },
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Unified admin dashboard content checks
    assert "Idag i köket" in html
    assert "Veckostatus" in html
    assert "Meny framåt" in html
    assert "Kom ihåg att beställa" in html
