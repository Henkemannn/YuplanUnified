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
def test_weekview_site_overview_phase1(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_a = str(uuid.uuid4())
    dep_b = str(uuid.uuid4())
    year, week = 2025, 47

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Site and departments
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_a, "s": site_id, "n": "Avd A"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_b, "s": site_id, "n": "Avd B"})
            db.commit()
            # Dishes
            d1 = Dish(tenant_id=1, name="Köttbullar", category=None)
            d2 = Dish(tenant_id=1, name="Fiskgratäng", category=None)
            d3 = Dish(tenant_id=1, name="Vaniljpudding", category=None)
            d4 = Dish(tenant_id=1, name="Soppa", category=None)
            d5 = Dish(tenant_id=1, name="Pannkakor", category=None)
            db.add_all([d1, d2, d3, d4, d5])
            db.commit()
            db.refresh(d1); db.refresh(d2); db.refresh(d3); db.refresh(d4); db.refresh(d5)
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            # Department-independent menu variants (site-wide)
            # Mon lunch alt1/alt2/dessert, Tue dinner alt1, Thu lunch alt1
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="dessert", dish_id=d3.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="tue", meal="dinner", variant_type="alt1", dish_id=d4.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="thu", meal="lunch", variant_type="alt1", dish_id=d5.id)
        finally:
            db.close()

    # Materialize baseline + set data for Dep A
    base_a = f"/api/weekview?year={year}&week={week}&department_id={dep_a}"
    r0a = client_admin.get(base_a, headers=_h("admin"))
    assert r0a.status_code == 200 and ETAG_RE.match(r0a.headers.get("ETag") or "")
    etag_a = r0a.headers.get("ETag")

    # Alt2 on Mon (1) and Wed (3); residents lunch (Mon 10) and dinner (Tue 5)
    r_alt2_a = client_admin.patch(
        "/api/weekview/alt2",
        json={"tenant_id": 1, "department_id": dep_a, "year": year, "week": week, "days": [1, 3]},
        headers={**_h("editor"), "If-Match": etag_a},
    )
    assert r_alt2_a.status_code in (200, 201)
    etag_a2 = r_alt2_a.headers.get("ETag") or etag_a

    r_res_a = client_admin.patch(
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "department_id": dep_a,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 1, "meal": "lunch", "count": 10},
                {"day_of_week": 2, "meal": "dinner", "count": 5},
            ],
        },
        headers={**_h("admin"), "If-Match": etag_a2},
    )
    assert r_res_a.status_code in (200, 201)

    # Materialize baseline + set data for Dep B: dinner residents only; no Alt2
    base_b = f"/api/weekview?year={year}&week={week}&department_id={dep_b}"
    r0b = client_admin.get(base_b, headers=_h("admin"))
    assert r0b.status_code == 200 and ETAG_RE.match(r0b.headers.get("ETag") or "")
    etag_b = r0b.headers.get("ETag")
    r_res_b = client_admin.patch(
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "department_id": dep_b,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 2, "meal": "dinner", "count": 8},  # Tue dinner
            ],
        },
        headers={**_h("admin"), "If-Match": etag_b},
    )
    assert r_res_b.status_code in (200, 201)

    # Call overview UI
    r_ui = client_admin.get(
        f"/ui/weekview_overview?site_id={site_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # Both department names
    assert "Avd A" in html and "Avd B" in html

    # Weekly totals text for A and B
    assert "Lunch: 10" in html and "Middag: 5" in html  # Dep A
    assert "Middag: 8" in html  # Dep B

    # Menu icons present for days with menu data (🍽 icon rendered with class menu-icon)
    assert html.count("menu-icon") >= 2  # Mon lunch, Tue dinner, Thu lunch at least

    # Alt2 markers: only for Dep A on 2 days (Mon, Wed)
    assert html.count("alt2-gul") == 2

    # Link to department-level Weekview exists
    assert f"/ui/weekview?site_id={site_id}&department_id={dep_a}&year={year}&week={week}" in html
