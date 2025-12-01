from sqlalchemy import text

def test_admin_ui_dashboard_lists_departments(client_admin):
    app = client_admin.application
    from core.db import get_session
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('11111111-2222-3333-4444-555555555555','TestSite',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','11111111-2222-3333-4444-555555555555','Avd 1','fixed',0,0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('ffffffff-1111-2222-3333-444444444444','11111111-2222-3333-4444-555555555555','Avd 2','fixed',0,0)"))
            db.commit()
        finally:
            db.close()
    resp = client_admin.get("/ui/admin/dashboard", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Admin" in html
    assert "Avdelningar" in html
    assert "/ui/portal/department/week?department_id=" in html
