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


def test_weekly_pdf_export_happy_path(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    year = 2025
    week = 48

    resp = client.get(
        f"/ui/reports/weekly.pdf?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "application/pdf"
    cd = resp.headers.get("Content-Disposition", "")
    assert f"veckorapport_v{week}_{year}.pdf" in cd
    body = resp.data
    assert body and len(body) > 50
    assert body.startswith(b"%PDF")


essentially_empty_week = (2099, 1)


def test_weekly_pdf_export_no_data(app_session):
    client = app_session.test_client()
    _seed_site_and_department()

    site_id = "00000000-0000-0000-0000-000000000000"
    year, week = essentially_empty_week

    resp = client.get(
        f"/ui/reports/weekly.pdf?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "application/pdf"
    cd = resp.headers.get("Content-Disposition", "")
    assert f"veckorapport_v{week}_{year}.pdf" in cd
    body = resp.data
    assert body and body.startswith(b"%PDF")
