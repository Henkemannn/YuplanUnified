from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def test_weekly_excel_export_happy_path(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    year = 2025
    week = 48
    resp = client.get(
        f"/ui/reports/weekly.xlsx?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    cd = resp.headers.get("Content-Disposition", "")
    assert ".xlsx" in cd
    assert f"veckorapport_v{week}_{year}.xlsx" in cd
    body = resp.data
    assert body and len(body) > 100
    assert body.startswith(b"PK")


def test_weekly_excel_export_no_data(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    year = 2099
    week = 1
    resp = client.get(
        f"/ui/reports/weekly.xlsx?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.data
    assert body and body.startswith(b"PK")
