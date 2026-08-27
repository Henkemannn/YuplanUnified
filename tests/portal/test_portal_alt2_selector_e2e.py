from sqlalchemy import text
from sqlalchemy import text


def _seed_minimal(db, site_id: str, dept_id: str):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER);
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        );
    """))
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
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS department_menu_choices(
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            site_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            meal TEXT NOT NULL DEFAULT 'lunch',
            selected_variant TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(tenant_id, site_id, department_id, year, week, weekday, meal)
        );
    """))
    db.execute(text("INSERT OR IGNORE INTO sites(id,name,tenant_id,version) VALUES(:i,'TestSite',1,0)"), {"i": site_id})
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:d, :s, 'Dept A', 'manual')"), {"d": dept_id, "s": site_id})
    db.commit()


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_portal_day_alt2_updates_explicit_choice_without_touching_weekview(client_admin):
    from core.db import get_session

    site_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    dept_id = "12345"
    year, week = 2025, 7
    with get_session() as db:
        _seed_minimal(db, site_id, dept_id)
        db.execute(
            text("INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled) VALUES(:s, :d, :y, :w, 2, 0)"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        )
        db.commit()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    before = None
    with get_session() as db:
        before = db.execute(
            text("SELECT enabled FROM weekview_alt2_flags WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND day_of_week=2"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()

    r_post = client_admin.post(
        f"/ui/portal/week/{year}/{week}/{int(dept_id)}/day/2",
        data={"selected_alt": "2"},
        headers=_h("admin"),
        follow_redirects=False,
    )
    assert r_post.status_code in (302, 303, 200)

    r_view = client_admin.get(
        f"/ui/portal/week/{year}/{week}/{int(dept_id)}",
        headers=_h("admin"),
    )
    assert r_view.status_code == 200
    html = r_view.get_data(as_text=True)
    assert ("Alt 2 vald" in html) or ("yp-badge yp-badge-warning" in html) or ("alt2" in html.lower())

    with get_session() as db:
        choice_row = db.execute(
            text("SELECT selected_variant FROM department_menu_choices WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND weekday=2"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()
        assert choice_row and str(choice_row[0]).lower() == "alt2"
        after = db.execute(
            text("SELECT enabled FROM weekview_alt2_flags WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND day_of_week=2"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()
        assert before and after and int(before[0]) == int(after[0]) == 0


def test_portal_day_alt1_leaves_weekview_alt2_intact(client_admin):
    from core.db import get_session

    site_id = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
    dept_id = "12346"
    year, week = 2025, 7
    with get_session() as db:
        _seed_minimal(db, site_id, dept_id)
        db.execute(
            text("INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled) VALUES(:s, :d, :y, :w, 2, 1)"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        )
        db.commit()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    r_post = client_admin.post(
        f"/ui/portal/week/{year}/{week}/{int(dept_id)}/day/2",
        data={"selected_alt": "1"},
        headers=_h("admin"),
        follow_redirects=False,
    )
    assert r_post.status_code in (302, 303, 200)

    with get_session() as db:
        choice_row = db.execute(
            text("SELECT selected_variant FROM department_menu_choices WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND weekday=2"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()
        assert choice_row and str(choice_row[0]).lower() == "alt1"
        flag_row = db.execute(
            text("SELECT enabled FROM weekview_alt2_flags WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND day_of_week=2"),
            {"s": site_id, "d": dept_id, "y": year, "w": week},
        ).fetchone()
        assert flag_row and int(flag_row[0]) == 1
