import uuid
from datetime import date

import pytest


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
def test_weekview_ui_renders_diets_and_mark_state(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 47

    # Seed site/department, a minimal menu to enable dinner columns, and diet defaults
    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish
    from core.admin_repo import DepartmentsRepo

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"),
                {"i": site_id, "n": "Varberg"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dep_id, "s": site_id, "n": "Avd Diet"},
            )
            db.commit()

            # Add a dinner dish somewhere in the week to show dinner columns/rows
            d_dinner = Dish(tenant_id=1, name="Soppa", category=None)
            db.add(d_dinner)
            db.commit(); db.refresh(d_dinner)
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="wed", meal="dinner", variant_type="alt1", dish_id=d_dinner.id)

            # Diet defaults: Gluten(2), Laktos(1)
            new_v = DepartmentsRepo().upsert_department_diet_defaults(
                dep_id,
                expected_version=0,
                items=[
                    {"diet_type_id": "Gluten", "default_count": 2},
                    {"diet_type_id": "Laktos", "default_count": 1},
                ],
            )
            assert isinstance(new_v, int)
        finally:
            db.close()

    # Baseline ETag
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Align session site context
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site_id, "next": "/"},
        headers=_h("admin"),
    )
    r0 = client_admin.get(base, headers=_h("admin"))
    assert r0.status_code == 200
    etag = r0.headers.get("ETag")
    assert etag

    # Mark Gluten on Monday lunch via PATCH
    mon = date.fromisocalendar(year, week, 1).isoformat()
    r_mark = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": mon,
            "meal": "lunch",
            "diet_type_id": "Gluten",
            "marked": True,
        },
    )
    assert r_mark.status_code in (200, 201)

    # Render UI and assert diets appear with correct classes/attributes
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # Diet names and counts
    assert "Gluten [2]" in html
    assert "Laktos [1]" in html

    # Gluten (Monday lunch) should have diet-marked and data-marked="true"
    assert "class=\"diet-pill diet-marked\"" in html or "diet-pill diet-marked" in html
    assert "data-diet-type-id=\"Gluten\"" in html
    assert "data-meal=\"lunch\"" in html
    assert "data-marked=\"true\"" in html

    # Accessibility: pills expose role and keyboard focus
    assert 'role="button"' in html
    assert 'tabindex="0"' in html

    # Root ETag present
    assert "data-etag=\"" in html
