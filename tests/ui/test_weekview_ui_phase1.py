import uuid

import pytest

ETAG_RE = __import__("re").compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_ui_renders_header_menu_and_alt2(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 45

    # Seed sites/departments and dishes/menu
    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd 1"})
            db.commit()
            # Dishes
            d1 = Dish(tenant_id=1, name="Köttbullar", category=None)
            d2 = Dish(tenant_id=1, name="Fiskgratäng", category=None)
            d3 = Dish(tenant_id=1, name="Vaniljpudding", category=None)
            d4 = Dish(tenant_id=1, name="Soppa", category=None)
            db.add_all([d1, d2, d3, d4])
            db.commit()
            db.refresh(d1); db.refresh(d2); db.refresh(d3); db.refresh(d4)
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            # Monday lunch alt1/alt2/dessert
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="dessert", dish_id=d3.id)
            # Tuesday dinner alt1
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="tue", meal="dinner", variant_type="alt1", dish_id=d4.id)
        finally:
            db.close()

    # Get baseline ETag then set alt2 + residents
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Align session site context
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site_id, "next": "/"},
        headers=_h("admin"),
    )
    r0 = client_admin.get(base, headers=_h("admin"))
    assert r0.status_code == 200 and ETAG_RE.match(r0.headers.get("ETag") or "")
    etag0 = r0.headers.get("ETag")

    r_alt2 = client_admin.patch(
        "/api/weekview/alt2",
        json={"tenant_id": 1, "site_id": site_id, "department_id": dep_id, "year": year, "week": week, "days": [1]},
        headers={**_h("editor"), "If-Match": etag0},
    )
    assert r_alt2.status_code in (200, 201)
    etag1 = r_alt2.headers.get("ETag") or etag0

    r_res = client_admin.patch(
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "site_id": site_id,
            "department_id": dep_id,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 1, "meal": "lunch", "count": 11},
                {"day_of_week": 2, "meal": "dinner", "count": 7},
            ],
        },
        headers={**_h("admin"), "If-Match": etag1},
    )
    assert r_res.status_code in (200, 201)

    # Render UI
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    # Header
    assert f"Vecka {week} – Avd 1, Varberg" in html
    # Menu
    assert "Köttbullar" in html and "Fiskgratäng" in html and "Vaniljpudding" in html
    # Alt2 highlight present on lunch alt2 cell
    assert "alt2-gul" in html
    # Dinner columns present (we added a dinner dish on Tue) using new label
    assert "Kvällsmat Alt 1" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_ui_no_dinner_hides_columns(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 46

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd 2"})
            db.commit()
            # Only lunch dishes (no dinner set)
            d1 = Dish(tenant_id=1, name="Pytt i panna", category=None)
            db.add(d1)
            db.commit(); db.refresh(d1)
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
        finally:
            db.close()

    # Ensure weekview materialized
    r0 = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r0.status_code == 200

    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Vecka" in html and "Avd 2" in html and "Varberg" in html
    # Dinner columns hidden when no dinner data
    assert "Kvällsmat Alt 1" not in html and "Kvällsmat Alt 2" not in html
