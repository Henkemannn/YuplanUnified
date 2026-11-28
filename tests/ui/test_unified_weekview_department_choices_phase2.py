from tests._auth_site_helpers import login_bound_user
from datetime import date as _date

from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site = conn.execute(text("SELECT id FROM sites WHERE id='38c632e3-0825-58b5-8fdd-af71b04f8e57'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, tenant_id, name) VALUES ('38c632e3-0825-58b5-8fdd-af71b04f8e57', 1, 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='f608ffc6-691c-5b4d-ac8e-37ddb4a390cc'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('f608ffc6-691c-5b4d-ac8e-37ddb4a390cc', '38c632e3-0825-58b5-8fdd-af71b04f8e57', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def _ensure_menu_for_week(tenant_id: int, site_id: str, year: int, week: int) -> None:
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish
    from unittest.mock import patch

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id, site_id, week, year)
    db = get_new_session()
    try:
        d = Dish(tenant_id=tenant_id, site_id=site_id, name="Test Lunch", category=None)
        db.add(d)
        db.commit()
        db.refresh(d)
        dish_id = d.id
    finally:
        db.close()
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_id)
    with patch("core.commun_builder_publication.CommunBuilderPublicationService.get_publication_for_week", return_value=None), patch("core.commun_builder_publication.CommunBuilderPublicationService.publish_week", return_value=object()), patch("core.commun_builder_publication.CommunBuilderPublicationService.republish_week", return_value=object()):
        svc.publish_menu(tenant_id, menu.id)


def test_weekview_reflects_department_registration_choice(app_session):
    client = app_session.test_client()
    _seed_site_and_department()
    site_id = "38c632e3-0825-58b5-8fdd-af71b04f8e57"
    login_bound_user(client, site_id=site_id)
    department_id = "f608ffc6-691c-5b4d-ac8e-37ddb4a390cc"
    year = 2025
    week = 48
    tid = 1

    _ensure_menu_for_week(tid, site_id, year, week)
    monday = _date.fromisocalendar(year, week, 1).isoformat()

    # Register lunch
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

    # Kitchen weekview should show ✓ Registrerad
    rv = client.get(
        f"/ui/weekview?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "✓ Registrerad" in html or "Registrerad" in html
