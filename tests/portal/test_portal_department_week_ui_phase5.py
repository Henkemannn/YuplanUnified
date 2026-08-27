from sqlalchemy import text


def test_portal_department_week_ui_phase5_conflict_modal_present(client_admin):
    year=2025; week=47
    dept_id="11111111-2222-3333-4444-555555555555"
    site_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:s, 'Site', 1, 0)"), {"s": site_id})
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:d, :s, 'Avd 1', 'manual')"), {"d": dept_id, "s": site_id})
        db.commit()
    finally:
        db.close()
    resp = client_admin.get(f"/ui/portal/department/week?year={year}&week={week}", environ_overrides={"test_claims": {"department_id": dept_id}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Modal structure present
    assert 'id="portal-conflict-overlay"' in html
    assert 'Informationen är utdaterad' in html
    # Action buttons now include refresh, reload, dismiss
    assert 'Försök igen' in html
    assert 'Ladda om' in html
    assert 'Fortsätt ändå' in html
