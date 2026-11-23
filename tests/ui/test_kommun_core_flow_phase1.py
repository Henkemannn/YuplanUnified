from datetime import date as _date
import uuid

from sqlalchemy import text
from werkzeug.security import generate_password_hash

def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'"))
        if not site.fetchone():
            conn.execute(
                text(
                    "INSERT INTO sites (id, name, tenant_id, version) "
                    "VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site', 1, 0)"
                )
            )
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def _login_bound_admin(client, site_id: str) -> None:
    from core.db import get_session
    from core.models import User

    email = f"kommun-{uuid.uuid4().hex}@example.test"
    password = "KommunPassw0rd!"
    db = get_session()
    try:
        user = User(
            tenant_id=1,
            email=email,
            username=email,
            password_hash=generate_password_hash(password),
            role="admin",
            auth_version=1,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.execute(text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"), {"user_id": user.id})
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, 1, :site_id)"
            ),
            {"user_id": user.id, "site_id": site_id},
        )
        db.commit()
        user_id = user.id
        auth_version = user.auth_version
    finally:
        db.close()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["user_id"] == user_id
        assert session["tenant_id"] == 1
        assert session["site_id"] == site_id
        assert session["auth_version"] == auth_version


def _ensure_menu_for_week(tenant_id: int, site_id: str, year: int, week: int) -> None:
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish
    from unittest.mock import patch

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id, site_id, week, year)
    db = get_new_session()
    try:
        d = Dish(tenant_id=tenant_id, site_id=site_id, name="Köttbullar", category=None)
        db.add(d)
        db.commit()
        db.refresh(d)
        dish_id = d.id
    finally:
        db.close()
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_id)
    with patch("core.commun_builder_publication.CommunBuilderPublicationService.get_publication_for_week", return_value=None), patch("core.commun_builder_publication.CommunBuilderPublicationService.publish_week", return_value=object()), patch("core.commun_builder_publication.CommunBuilderPublicationService.republish_week", return_value=object()):
        svc.publish_menu(tenant_id, menu.id)


def _seed_weekview_expected_for_report(department_id: str, year: int, week: int) -> None:
    """Ensure ReportService sees at least one expected lunch (via weekview_items)."""
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS weekview_items (
                    id TEXT PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    department_id TEXT NOT NULL,
                    local_date TEXT NOT NULL,
                    meal TEXT NOT NULL,
                    title TEXT NOT NULL,
                    notes TEXT,
                    status TEXT,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                )
                """
            )
        )
        monday = _date.fromisocalendar(year, week, 1).isoformat()
        # Insert a weekview item with non-empty title to count as expected
        conn.execute(
            text(
                """
                INSERT INTO weekview_items (id, tenant_id, department_id, local_date, meal, title, notes, status, version, updated_at)
                VALUES (:id, :tid, :dep, :date, 'lunch', 'Alt1', NULL, NULL, 0, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "tid": 1,
                "dep": department_id,
                "date": monday,
            },
        )
        conn.commit()
    finally:
        conn.close()


def test_end_to_end_department_choice_to_weekly_report(app_session):
    client = app_session.test_client()
    _seed_site_and_department()
    site_id = "00000000-0000-0000-0000-000000000000"
    department_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 48
    tid = 1
    _login_bound_admin(client, site_id)

    _ensure_menu_for_week(tid, site_id, year, week)
    _seed_weekview_expected_for_report(department_id, year, week)

    monday = _date.fromisocalendar(year, week, 1).isoformat()
    # Department registers lunch
    client.post(
        "/ui/weekview/registration",
        data={
            "site_id": site_id,
            "department_id": department_id,
            "year": str(year),
            "week": str(week),
            "date": monday,
            "meal_type": "lunch",
            "registered": "1",
        },
        follow_redirects=True,
    )

    # Kitchen weekview shows Registered
    wk = client.get(
        f"/ui/weekview?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
    )
    assert wk.status_code == 200
    assert "Registrerad" in wk.data.decode("utf-8")

    # Weekly report HTML shows full coverage (100 procent) for the registered lunch
    rep = client.get(
        f"/ui/reports/weekly?site_id={site_id}&year={year}&week={week}",
    )
    assert rep.status_code == 200
    html = rep.data.decode("utf-8")
    assert "Avd Alpha" in html
    assert "100 procent" in html
