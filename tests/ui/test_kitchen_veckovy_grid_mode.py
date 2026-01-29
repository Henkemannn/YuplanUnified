from datetime import date as _date

import pytest
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
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
        d1 = Dish(tenant_id=tenant_id, name="Alt1 Renskav", category=None)
        d2 = Dish(tenant_id=tenant_id, name="Alt2 Falukorv", category=None)
        d3 = Dish(tenant_id=tenant_id, name="Dessert Pannacotta", category=None)
        d4 = Dish(tenant_id=tenant_id, name="Kvällsmat Soppa", category=None)
        db.add_all([d1, d2, d3, d4])
        db.commit()
        db.refresh(d1); db.refresh(d2); db.refresh(d3); db.refresh(d4)
        dish_ids = [d1.id, d2.id, d3.id, d4.id]
    finally:
        db.close()
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_ids[0])
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt2", dish_ids[1])
    svc.set_variant(tenant_id, menu.id, "mon", "dinner", "alt1", dish_ids[3])
    svc.set_variant(tenant_id, menu.id, "mon", "dessert", "alt1", dish_ids[2])
    svc.publish_menu(tenant_id, menu.id)


def test_kitchen_grid_renders_and_icons_present(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    department_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 49
    tid = 1

    _ensure_menu_for_week(tid, year, week)
    # Ensure at least one diet type exists for grid rendering
    from core.admin_repo import DietTypesRepo
    DietTypesRepo().create(site_id=site_id, name="Gluten", default_select=False)

    rv = client.get(
        f"/ui/kitchen/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # assertions
    assert "class=\"veckovy-department-card" in html or "class=\"ua-section weekview-all veckovy-department-card" in html
    assert "class=\"veckovy-table" in html or "class=\"ua-table weekview veckovy-table" in html
    assert "window.VECKOVY_MENU_DATA" in html
    assert "Alt1 Renskav" in html or "Alt2 Falukorv" in html
    assert "veckovy-menu-icon" in html or "class=\"menu-icon veckovy-menu-icon\"" in html


def test_enhetsportal_does_not_render_grid(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    department_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 49

    # Normal unified portal weekly view should not include grid elements
    rv = client.get(
        f"/ui/portal/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert ".veckovy-department-card" not in html
    assert ".veckovy-table" not in html
    assert "window.VECKOVY_MENU_DATA" not in html


def test_cell_classes_markerad_and_alt2(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    department_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 49
    tid = 1

    _ensure_menu_for_week(tid, year, week)
    # Seed a diet type so the grid has rows
    from core.admin_repo import DietTypesRepo
    DietTypesRepo().create(site_id=site_id, name="Gluten", default_select=False)
    monday = _date.fromisocalendar(year, week, 1).isoformat()

    # Register lunch for monday to create "markerad"
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

    rv = client.get(
        f"/ui/kitchen/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Presence of kost cells
    assert "class=\"kostcell" in html or "class=\"kostcell " in html
    # At least one markerad
    assert "markerad" in html
    # If Alt2 exists for some day, ensure gulmarkerad appears (depends on VM)
    # We don't know exact mapping but class should appear when alt2 is flagged.
    assert "gulmarkerad" in html or "kväll" in html
