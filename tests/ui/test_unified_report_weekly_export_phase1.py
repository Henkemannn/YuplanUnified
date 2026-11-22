import uuid

from sqlalchemy import text

from core.models import User


def _bound_client(app_session):
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "UNIQUE(user_id, tenant_id, site_id))"
            )
        )
        site_id = "00000000-0000-0000-0000-000000000000"
        department_id = "00000000-0000-0000-0000-000000000001"
        conn.execute(
            text(
                "INSERT OR IGNORE INTO sites (id, tenant_id, name) "
                "VALUES (:id, 1, 'Test Site')"
            ),
            {"id": site_id},
        )
        conn.execute(
            text("UPDATE sites SET tenant_id=1 WHERE id=:id"),
            {"id": site_id},
        )
        conn.execute(
            text(
                "INSERT OR IGNORE INTO departments "
                "(id, site_id, name, resident_count_mode, resident_count_fixed) "
                "VALUES (:id, :site_id, 'Avd Alpha', 'fixed', 5)"
            ),
            {"id": department_id, "site_id": site_id},
        )
        user = User(
            tenant_id=1,
            email=f"report-phase1-{uuid.uuid4().hex}@example.test",
            password_hash="fixture-only",
            role="admin",
            auth_version=1,
        )
        conn.add(user)
        conn.flush()
        conn.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, 1, :site_id)"
            ),
            {"user_id": user.id, "site_id": site_id},
        )
        conn.commit()
        client = app_session.test_client()
        with client.session_transaction() as session:
            session.update(
                {
                    "user_id": user.id,
                    "role": "admin",
                    "tenant_id": 1,
                    "site_id": site_id,
                    "auth_version": 1,
                }
            )
        return client, site_id
    finally:
        conn.close()


def test_weekly_report_csv_happy_path(app_session):
    client, site_id = _bound_client(app_session)

    # Use a deterministic year/week
    year = 2025
    week = 48

    # First render HTML (not strictly necessary) then fetch CSV
    resp_csv = client.get(
        f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}",
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
    client, site_id = _bound_client(app_session)

    # Choose a year/week unlikely to have data
    year = 2099
    week = 1

    resp_csv = client.get(
        f"/ui/reports/weekly.csv?site_id={site_id}&year={year}&week={week}",
    )
    assert resp_csv.status_code == 200
    assert resp_csv.headers.get("Content-Type", "").startswith("text/csv")

    body = resp_csv.data.decode("utf-8")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    # Header present
    assert len(lines) >= 1
    assert "site,department,year,week,meal,residents_total,debiterbar_specialkost,normal_count" in lines[0]
    # zero or more data lines are acceptable; no strict assertion on count
