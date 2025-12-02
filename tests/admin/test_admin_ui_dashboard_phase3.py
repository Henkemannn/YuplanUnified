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
    resp = client_admin.get("/ui/admin/dashboard?site_id=site-x", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Moduler" in html
    assert "Avdelningsportal" in html
    assert "Planera" in html
    assert "Rapport" in html
    # Placeholder cards present
    assert "Menyimport" in html and "Specialkost" in html and "Recept" in html and "Turnus" in html
