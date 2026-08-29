from sqlalchemy import text


def _seed(db, dept_id: str, site_id: str, year: int, week: int):
    db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            notes TEXT NULL,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
    """))
    db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:s, 'Site', 1, 0)"), {"s": site_id})
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s,:n,:note,'manual')"), {"i": dept_id, "s": site_id, "n": "Avd 1", "note": "Inga risrätter"})
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.commit()


def test_portal_links_removed_from_canonical_department_portal(client_admin):
    year=2025; week=47
    dept_id="11112222-3333-4444-5555-666677778888"; site_id="aaaa2222-bbbb-cccc-dddd-eeeeffff0000"
    from core.db import get_session
    db=get_session()
    try:
        _seed(db, dept_id, site_id, year, week)
    finally:
        db.close()
    resp = client_admin.get(f"/ui/portal/department/week?year={year}&week={week}", environ_overrides={"test_claims": {"department_id": dept_id}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Öppna veckovy" not in html
    assert "Visa rapport" not in html
    assert "/ui/weekview?" not in html
    assert "/ui/reports/weekview?" not in html
