from sqlalchemy import text

def test_admin_ui_dashboard_phase4_feature_flag_gating(client_admin):
    app = client_admin.application
    # Disable one module flag (planera) and ensure card omitted
    with app.app_context():
        # Ensure feature registry exists
        reg = getattr(app, 'feature_registry', None)
        if reg and not reg.has('ff.planera.enabled'):
            reg.add('ff.planera.enabled')
        if reg:
            reg.set('ff.planera.enabled', False)
        # Seed minimal site/department tables for dashboard
        from core.db import get_session
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-flag','FlagSite',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('dep-flag','site-flag','Avd Flag','fixed',0,0)"))
            db.commit()
        finally:
            db.close()
    # Use canonical admin route; provide active site via header in tests
    resp = client_admin.get(
        "/ui/admin",
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "1",
            "X-Site-Id": "site-flag",
        },
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Unified admin dashboard content
    assert "Idag i köket" in html and "Veckostatus" in html
    # Legacy module card header should not exist in unified dashboard
    assert "<h3>Planera</h3>" not in html
