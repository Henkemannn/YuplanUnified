from flask.testing import FlaskClient
from sqlalchemy import text
import re

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
from core.app_factory import create_app
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.db import get_session, get_new_session
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB
from core.models import Dish


def _seed_site(db, site_id: str):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": f"K3 {site_id}"})
        db.commit()


def test_kitchen_menu_overview_renders():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_site(db, "site-menu")
        finally:
            db.close()
        svc = MenuServiceDB()
        year = 2026
        week = 5
        site_id = "site-menu"
        menu = svc.create_or_get_menu(1, site_id, week, year)
        db2 = get_new_session()
        try:
            d1 = Dish(tenant_id=1, name="Alt1 Gryta", category=None)
            d2 = Dish(tenant_id=1, name="Alt2 Sallad", category=None)
            d3 = Dish(tenant_id=1, name="Dessert Frukt", category=None)
            d4 = Dish(tenant_id=1, name="Kvällsmat Soppa", category=None)
            db2.add_all([d1, d2, d3, d4])
            db2.commit()
            db2.refresh(d1)
            db2.refresh(d2)
            db2.refresh(d3)
            db2.refresh(d4)
        finally:
            db2.close()
        svc.set_variant(1, menu.id, "mon", "lunch", "main", d1.id)
        svc.set_variant(1, menu.id, "mon", "lunch", "alt2", d2.id)
        svc.set_variant(1, menu.id, "mon", "lunch", "dessert", d3.id)
        svc.set_variant(1, menu.id, "mon", "dinner", "kvall", d4.id)
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/menu?site_id={site_id}&year={year}&week={week}", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    week_view = MenuServiceDB().get_week_view(1, site_id, week, year)
    assert week_view["days"]["mon"]["dinner"]["main"]["dish_name"] == "Kvällsmat Soppa"
    assert "Menyöversikt" in html
    assert "Kvällsmat" in html
    assert "Dessert" in html
    assert "Alt 2" in html
    assert "yp-pill--alt2" in html
    assert "data-action=\"print\"" in html
    assert re.search(r"app-shell__nav-item[^>]*>\s*Menyöversikt\s*<", html)
    assert 'app-shell__nav-item">Admin<' not in html


def test_kitchen_menu_overview_prefers_published_builder_projection():
    app = create_app()
    app.config.update({"TESTING": True})
    site_id = "site-menu-builder"
    year = 2026
    week = 42

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
        db = get_session()
        try:
            _seed_site(db, site_id)
        finally:
            db.close()
        svc = MenuServiceDB()
        menu = svc.create_or_get_menu(1, site_id, week, year)

        builder_flow, composition_service = _build_builder_menu_context_flow()
        app.extensions["builder_menu_context_flow"] = builder_flow
        app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-overview", site_id=site_id, week_key="2026-W42", version=1, status="published")
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
                    menu_id="builder-menu-overview",
                    day=day,
                    display_label=f"{day} {index}",
                    sort_order=sort_order,
                )
                builder_flow.update_composition_menu_row(
                    menu_id="builder-menu-overview",
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
            builder_menu_id="builder-menu-overview",
            source="manual",
        )
        menu_service = MenuServiceDB()
        menu_service.publish_menu(tenant_id=1, menu_id=menu.id)

    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/menu?site_id={site_id}&year={year}&week={week}", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Ingen meny ännu" not in html
    assert "Mon Alt1" in html
    assert "Mon Alt2" in html
    assert "Mon Dessert" in html
    assert "Mon Dinner" in html
    assert "Sun Alt1" in html
    assert "Sun Dessert" in html
    assert "Sun Dinner" in html
    assert "Sun Alt2" not in html
