from tests._auth_site_helpers import login_bound_user
from datetime import date as _date
from uuid import uuid4

from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    site_id, department_id = str(uuid4()), str(uuid4())
    conn = get_session()
    try:
        conn.execute(text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, 1, 'Test Site')"), {"site": site_id})
        conn.execute(
            text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) "
                 "VALUES (:department, :site, 'Avd Alpha', 'fixed', 5)"),
            {"department": department_id, "site": site_id},
        )
        conn.commit()
        return site_id, department_id
    finally:
        conn.close()


def _ensure_menu_for_week(tenant_id: int, site_id: str, year: int, week: int, dish_name: str = "Test Lunch") -> None:
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish
    from unittest.mock import patch

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id, site_id, week, year)
    # Create a dish for alt1
    db = get_new_session()
    try:
        d = Dish(tenant_id=tenant_id, site_id=site_id, name=dish_name, category=None)
        db.add(d)
        db.commit()
        db.refresh(d)
        dish_id = d.id
    finally:
        db.close()
    # Set Monday (Mon) lunch alt1
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_id)
    # Publish menu
    with patch("core.commun_builder_publication.CommunBuilderPublicationService.get_publication_for_week", return_value=None), patch("core.commun_builder_publication.CommunBuilderPublicationService.publish_week", return_value=object()), patch("core.commun_builder_publication.CommunBuilderPublicationService.republish_week", return_value=object()):
        svc.publish_menu(tenant_id, menu.id)


def test_portal_department_week_choice_happy_path(app_session):
    client = app_session.test_client()
    site_id, department_id = _seed_site_and_department()
    login_bound_user(client, site_id=site_id)
    year = 2025
    week = 48
    tid = 1

    _ensure_menu_for_week(tid, site_id, year, week)

    # Initial GET: portal week should render lunch block (menu exists)
    r0 = client.get(
        f"/portal/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert r0.status_code == 200
    html0 = r0.data.decode("utf-8")
    assert "LUNCH" in html0
    # Initially unregistered badge may show "Ej gjord"
    assert "Ej gjord" in html0

    # Choose: mark Monday lunch as registered via POST
    monday = _date.fromisocalendar(year, week, 1).isoformat()
    resp = client.post(
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
    assert resp.status_code == 200

    # Reload portal week: now should reflect Registrerad badge
    r1 = client.get(
        f"/portal/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert r1.status_code == 200
    html1 = r1.data.decode("utf-8")
    assert "Registrerad" in html1


def test_portal_department_week_choice_persists(app_session):
    client = app_session.test_client()
    site_id, department_id = _seed_site_and_department()
    login_bound_user(client, site_id=site_id)
    year = 2025
    week = 48
    tid = 1

    _ensure_menu_for_week(tid, site_id, year, week)
    monday = _date.fromisocalendar(year, week, 1).isoformat()
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

    # Reload shows persisted state
    r = client.get(
        f"/portal/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert r.status_code == 200
    assert "Registrerad" in r.data.decode("utf-8")
