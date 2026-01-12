from sqlalchemy import text

def test_admin_ui_dashboard_phase3_modules_cards(client_admin):
    app = client_admin.application
    from core.db import get_session
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-x','Varberg',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('dep-x','site-x','Avd X','fixed',0,0)"))
            db.commit()
        finally:
            db.close()
    # Use canonical admin route; provide active site via header in tests
    resp = client_admin.get(
        "/ui/admin",
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "1",
            "X-Site-Id": "site-x",
        },
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Unified admin dashboard presence checks
    assert "Idag i köket" in html
    assert "Veckostatus" in html
    assert "Meny framåt" in html
    assert "Kommunikation mellan avdelningar" in html
