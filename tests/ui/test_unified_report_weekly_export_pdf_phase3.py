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
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
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
        conn.execute(text("UPDATE sites SET tenant_id=1 WHERE id=:id"), {"id": site_id})
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
            email=f"report-phase3-{uuid.uuid4().hex}@example.test",
            password_hash="fixture-only",
            role="admin",
            auth_version=1,
        )
        conn.add(user)
        conn.flush()
        conn.execute(text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"), {"user_id": user.id})
        conn.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": user.id, "tenant_id": 1, "site_id": site_id},
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


def test_weekly_pdf_export_happy_path(app_session):
    client, site_id = _bound_client(app_session)

    year = 2025
    week = 48

    resp = client.get(
        f"/ui/reports/weekly.pdf?site_id={site_id}&year={year}&week={week}",
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
    client, site_id = _bound_client(app_session)

    year, week = essentially_empty_week

    resp = client.get(
        f"/ui/reports/weekly.pdf?site_id={site_id}&year={year}&week={week}",
    )
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "application/pdf"
    cd = resp.headers.get("Content-Disposition", "")
    assert f"veckorapport_v{week}_{year}.pdf" in cd
    body = resp.data
    assert body and body.startswith(b"%PDF")
