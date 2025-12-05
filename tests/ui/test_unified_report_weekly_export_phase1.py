from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'")).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'")).fetchone()
        if not dep:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def test_weekly_report_csv_happy_path(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    # Use a deterministic year/week
    site_id = "00000000-0000-0000-0000-000000000000"
    year = 2025
    week = 48

    # First render HTML (not strictly necessary) then fetch CSV
    resp_csv = client.get(
        f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp_csv.status_code == 200
    assert resp_csv.headers.get("Content-Type", "").startswith("text/csv")
    cd = resp_csv.headers.get("Content-Disposition", "")
    assert f"veckorapport_v{week}_{year}.csv" in cd

    body = resp_csv.data.decode("utf-8")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    assert len(lines) >= 1
    # Header row
    assert "site,department,year,week,meal,residents_total,debiterbar_specialkost,normal_count" in lines[0]
    # At least one data row mentions department name or week number
    assert any("Avd Alpha" in ln or f",{week}," in ln for ln in lines[1:])


def test_weekly_report_csv_no_data(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    # Choose a year/week unlikely to have data
    year = 2099
    week = 1

    resp_csv = client.get(
        f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp_csv.status_code == 200
    assert resp_csv.headers.get("Content-Type", "").startswith("text/csv")

    body = resp_csv.data.decode("utf-8")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    # Header present
    assert len(lines) >= 1
    assert "site,department,year,week,meal,residents_total,debiterbar_specialkost,normal_count" in lines[0]
    # zero or more data lines are acceptable; no strict assertion on count
