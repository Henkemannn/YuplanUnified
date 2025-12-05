from datetime import date as _date

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


def _ensure_menu_for_week(tenant_id: int, year: int, week: int) -> None:
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id, week, year)
    db = get_new_session()
    try:
        d = Dish(tenant_id=tenant_id, name="Köttbullar", category=None)
        db.add(d)
        db.commit()
        db.refresh(d)
        dish_id = d.id
    finally:
        db.close()
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_id)
    svc.publish_menu(tenant_id, menu.id)


def _seed_weekview_expected_for_report(department_id: str, year: int, week: int) -> None:
    """Ensure ReportService sees at least one expected lunch (via weekview_items)."""
    from core.db import get_session
    conn = get_session()
    try:
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

    _ensure_menu_for_week(tid, year, week)
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
        headers=HEADERS,
        follow_redirects=True,
    )

    # Kitchen weekview shows Registered
    wk = client.get(
        f"/ui/weekview?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert wk.status_code == 200
    assert "Registrerad" in wk.data.decode("utf-8")

    # Weekly report HTML shows full coverage (100%) for the registered lunch
    rep = client.get(
        f"/ui/reports/weekly?site_id={site_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rep.status_code == 200
    html = rep.data.decode("utf-8")
    assert "Avd Alpha" in html
    assert "100%" in html
