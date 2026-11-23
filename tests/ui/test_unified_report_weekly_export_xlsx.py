from sqlalchemy import text
import uuid

from core.db import get_session
from core.models import User


def _bind_admin_to_site(client, site_id: str) -> None:
    with client.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "DELETE FROM kitchen_user_sites "
                    "WHERE user_id NOT IN (SELECT id FROM users)"
                )
            )
            user = User(
                tenant_id=1,
                username=f"xlsx-{uuid.uuid4().hex}@example.test",
                email=f"xlsx-{uuid.uuid4().hex}@example.test",
                password_hash="fixture-only",
                role="admin",
                is_active=True,
                auth_version=1,
                must_change_password=False,
            )
            db.add(user)
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": user.id, "site_id": site_id},
            )
            db.commit()
            user_id = user.id
        finally:
            db.close()
    with client.session_transaction() as session:
        session.update(
            {
                "user_id": user_id,
                "role": "admin",
                "tenant_id": 1,
                "site_id": site_id,
                "auth_version": 1,
            }
        )


def _seed_site_and_department(client):
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000000"
        site = conn.execute(text("SELECT id FROM sites WHERE id=:site_id"), {"site_id": site_id})\
            .fetchone()
        if not site:
            conn.execute(
                text("INSERT INTO sites (id, name, tenant_id) VALUES (:site_id, 'Test Site', 1)"),
                {"site_id": site_id},
            )
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'"))\
            .fetchone()
        if not dep:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()
    _bind_admin_to_site(client, site_id)


def test_weekly_report_xlsx_happy_path(client_admin):
    _seed_site_and_department(client_admin)

    site_id = "00000000-0000-0000-0000-000000000000"
    year = 2025
    week = 48

    resp_xlsx = client_admin.get(
        f"/ui/reports/weekly.xlsx?site_id={site_id}&year={year}&week={week}",
    )
    assert resp_xlsx.status_code == 200
    assert resp_xlsx.headers.get("Content-Type", "").startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    cd = resp_xlsx.headers.get("Content-Disposition", "")
    assert f"veckorapport_v{week}_{year}.xlsx" in cd

    # Read workbook from response
    from io import BytesIO
    buf = BytesIO(resp_xlsx.data)
    try:
        from openpyxl import load_workbook
    except Exception:
        assert False, "openpyxl not available for XLSX test"
    wb = load_workbook(buf)
    ws = wb.active

    # Header row check (must match labels used in exporter)
    header = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    assert header == [
        "Site",
        "Avdelning",
        "År",
        "Vecka",
        "Måltid",
        "Boende totalt",
        "Gjorda specialkoster",
        "Normalkost",
    ]

    # There should be at least two data rows (lunch/dinner for the department)
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 2
    # Ensure debiterbar specialkost and normal count columns exist and are numeric
    for row in data_rows:
        residents_total = row[5] or 0
        debiterbar = row[6] or 0
        normal = row[7] or 0
        assert isinstance(debiterbar, (int, float))
        assert isinstance(normal, (int, float))
        # Normal should equal residents_total - debiterbar (non-negative)
        assert normal == max(0, (residents_total or 0) - (debiterbar or 0))
