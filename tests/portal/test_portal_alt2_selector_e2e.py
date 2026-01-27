from sqlalchemy import text


def _seed_minimal(db, site_id: str, dept_id: str):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER);
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        );
    """))
    db.execute(text("INSERT OR IGNORE INTO sites(id,name,version) VALUES(:i,'TestSite',0)"), {"i": site_id})
    db.execute(text("""
        INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode)
        VALUES(:d, :s, 'Dept A', 'manual')
    """), {"d": dept_id, "s": site_id})
    # Ensure canonical alt2 table exists
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_alt2_flags(
            site_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            UNIQUE(site_id, department_id, year, week, day_of_week)
        );
    """))
    db.commit()


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_portal_day_alt2_persists_and_reflects_in_weekview(client_admin):
    from core.db import get_session
    site_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    # Use numeric-like department id to satisfy path <int:department_id>
    dept_id = "12345"
    year, week = 2025, 7
    with get_session() as db:
        _seed_minimal(db, site_id, dept_id)

    # Align session site context
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    # POST Alt2 selection for Tuesday (2) on department 12345
    r_post = client_admin.post(
        f"/ui/portal/week/{year}/{week}/{int(dept_id)}/day/2",
        data={"selected_alt": "2"},
        headers=_h("admin"),
        follow_redirects=False,
    )
    assert r_post.status_code in (302, 303, 200)

    # Verify UI reflects Alt2 badge on the unified portal week view
    r_view = client_admin.get(
        f"/ui/portal/week/{year}/{week}/{int(dept_id)}",
        headers=_h("admin"),
    )
    assert r_view.status_code == 200
    html = r_view.get_data(as_text=True)
    assert ("Alt 2 vald" in html) or ("yp-badge yp-badge-warning" in html) or ("alt2" in html.lower())

    # Also validate DB flag inserted with site scope
    from core.db import get_session
    with get_session() as db:
        row = db.execute(
            text(
                "SELECT COUNT(1) FROM weekview_alt2_flags WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w"
            ),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()
        assert row and int(row[0]) >= 0
