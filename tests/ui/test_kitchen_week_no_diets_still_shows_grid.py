from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_dep_with_no_diets(site_id: str, dep_id: str, residents_fixed: int, year: int, week: int, alt2_day: int):
    from core.db import get_session
    conn = get_session()
    try:
        # Ensure minimal core tables exist; in SQLite, they should already by migrations/tests
        # Create site and department
        row = conn.execute(text("SELECT 1 FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if not row:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:id, 'K3 Test Site')"), {"id": site_id})
        row = conn.execute(text("SELECT 1 FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
        if not row:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES (:id, :sid, 'Avd K3', 'fixed', :rc, 0)"), {"id": dep_id, "sid": site_id, "rc": residents_fixed})
        else:
            conn.execute(text("UPDATE departments SET resident_count_fixed=:rc, resident_count_mode='fixed' WHERE id=:id"), {"id": dep_id, "rc": residents_fixed})
        # Ensure weekview_alt2_flags exists and insert a flag for Monday
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                site_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                UNIQUE (site_id, department_id, year, week, day_of_week)
            );
            """
        ))
        conn.execute(text(
            """
            INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled)
            VALUES(:site_id, :dep_id, :year, :week, :dow, 1)
            """
        ), {"site_id": site_id, "dep_id": dep_id, "year": year, "week": week, "dow": alt2_day})
        conn.commit()
    finally:
        conn.close()


def test_kitchen_week_no_diets_still_shows_grid(app_session):
    client = app_session.test_client()
    site_id = 'site-k3-1'
    dep_id = 'dep-k3-1'
    year = 2026
    week = 8
    _seed_site_dep_with_no_diets(site_id, dep_id, residents_fixed=7, year=year, week=week, alt2_day=1)

    rv = client.get(f"/ui/kitchen/week?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode('utf-8')

    # a) department card/table exists
    assert f'data-department-id="{dep_id}"' in html

    # b) Boende numbers appear (>0); resident_count_fixed=7 so expect '7' somewhere in Boende row
    assert '>7<' in html

    # c) Monday lunch Boende cell contains alt2 highlight class
    # Look for the boende row lunch cell marker with is-alt2
    assert 'class="kw-cell day-start is-alt2"' in html

    # d) Note appears below the table when no diets linked
    assert 'Inga specialkoster kopplade' in html
