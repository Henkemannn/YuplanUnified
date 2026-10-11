import uuid

import pytest

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB

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
            menu = app.menu_service.create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
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
    # Align session site context
    # Set session site context directly (selector is superuser-only)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    r0a = client_admin.get(base_a, headers=_h("admin"))
    assert r0a.status_code == 200 and ETAG_RE.match(r0a.headers.get("ETag") or "")
    etag_a = r0a.headers.get("ETag")

    # Alt2 on Mon (1) and Wed (3); residents lunch (Mon 10) and dinner (Tue 5)
    r_alt2_a = client_admin.patch(
        "/api/weekview/alt2",
        json={"tenant_id": 1, "site_id": site_id, "department_id": dep_a, "year": year, "week": week, "days": [1, 3]},
        headers={**_h("editor"), "If-Match": etag_a},
    )
    assert r_alt2_a.status_code in (200, 201)
    etag_a2 = r_alt2_a.headers.get("ETag") or etag_a

    r_res_a = client_admin.patch(
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "site_id": site_id,
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
            "site_id": site_id,
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

    # Weekly totals text for A and B (updated dinner label)
    assert "Lunch: 10" in html and "Kvällsmat: 5" in html  # Dep A
    assert "Kvällsmat: 8" in html  # Dep B

    # Menu icons present for days with menu data (🍽 icon rendered with class menu-icon)
    assert html.count("menu-icon") >= 2  # Mon lunch, Tue dinner, Thu lunch at least

    # Alt2 markers: only for Dep A on 2 days (Mon, Wed)
    assert html.count("alt2-gul") == 2

    # Link to department-level Weekview exists
    assert f"/ui/weekview?site_id={site_id}&department_id={dep_a}&year={year}&week={week}" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_site_overview_prefers_published_builder_projection(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_a = str(uuid.uuid4())
    year, week = 2026, 42

    from core.db import create_all, get_session
    from sqlalchemy import text

    def _build_builder_menu_context_flow():
        component_repository = InMemoryComponentRepository()
        composition_repository = InMemoryCompositionRepository()
        alias_repository = InMemoryCompositionAliasRepository()
        recipe_repository = InMemoryRecipeRepository()
        ingredient_repository = InMemoryRecipeIngredientLineRepository()
        builder_flow = BuilderFlow(
            component_service=ComponentService(repository=component_repository),
            composition_service=CompositionService(repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            component_alias_repository=InMemoryComponentAliasRepository(),
        )
        menu_context_flow = BuilderMenuContextFlow(
            menu_service=MenuService(composition_repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            recipe_repository=recipe_repository,
            ingredient_repository=ingredient_repository,
            library_flow=builder_flow,
        )
        return menu_context_flow, CompositionService(repository=composition_repository)

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_a, "s": site_id, "n": "Avd A"})
            db.commit()
            menu = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
        finally:
            db.close()

        builder_flow, composition_service = _build_builder_menu_context_flow()
        app.extensions["builder_menu_context_flow"] = builder_flow
        app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-weekview", site_id=site_id, week_key="2026-W42", version=1, status="published")
        for day, specs in {
            "monday": [
                (10, "comp_mon_1", "Mon Alt1"),
                (20, "comp_mon_2", "Mon Alt2"),
                (30, "comp_mon_3", "Mon Dessert"),
                (40, "comp_mon_4", "Mon Dinner"),
            ],
            "sunday": [
                (6010, "comp_sun_1", "Sun Alt1"),
                (6030, "comp_sun_3", "Sun Dessert"),
                (6040, "comp_sun_4", "Sun Dinner"),
            ],
        }.items():
            for index, (sort_order, composition_id, composition_name) in enumerate(specs, start=1):
                composition_service.create_composition(composition_id=composition_id, composition_name=composition_name)
                created = builder_flow.create_empty_menu_row(
                    menu_id="builder-menu-weekview",
                    day=day,
                    display_label=f"{day} {index}",
                    sort_order=sort_order,
                )
                builder_flow.update_composition_menu_row(
                    menu_id="builder-menu-weekview",
                    menu_detail_id=created.menu_detail_id,
                    day=day,
                    meal_slot=created.meal_slot,
                    composition_id=composition_id,
                    sort_order=sort_order,
                )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-weekview",
            source="manual",
        )
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=menu.id)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get(f"/ui/weekview_overview?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Ingen meny ännu" not in html
    assert "Mon Alt1" in html
    assert "Mon Alt2" in html
    assert "Mon Dessert" in html
    assert "Mon Dinner" in html
    assert "Sun Alt1" in html
    assert "Sun Dessert" in html
    assert "Sun Dinner" in html
    assert "Sun Alt2" not in html
