from __future__ import annotations

import pytest
from sqlalchemy import text

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
from core.db import get_session
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB


@pytest.fixture
def seed_portal_department_data(app_session):
    def _seed(
        *,
        dept_id: str,
        site_id: str,
        year: int,
        week: int,
        alt2_enabled_monday: int = 1,
        note: str = "Inga risrätter",
        legacy_menu_id: int = 201,
        legacy_alt1_name: str = "Legacy Pannbiff",
        legacy_alt2_name: str = "Legacy Fiskgratäng",
        legacy_dessert_name: str = "Legacy Fruktsallad",
        legacy_dinner_name: str = "Legacy Kvällsgröt",
    ) -> None:
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS departments(
                        id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        name TEXT,
                        resident_count_mode TEXT NOT NULL DEFAULT 'manual'
                    )
                    """
                )
            )
            db.execute(text("CREATE TABLE IF NOT EXISTS department_notes(department_id TEXT PRIMARY KEY, notes TEXT)"))
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,:n,'manual')"),
                {"i": dept_id, "s": site_id, "n": "Avd 1"},
            )
            db.execute(text("INSERT OR REPLACE INTO department_notes(department_id, notes) VALUES(:i,:n)"), {"i": dept_id, "n": note})
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"
                )
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))"
                )
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_alt2_flags(site_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, enabled INTEGER, UNIQUE(site_id,department_id,year,week,day_of_week))"
                )
            )
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'lunch',10)"), {"t": 1, "d": dept_id, "y": year, "w": week})
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'dinner',8)"), {"t": 1, "d": dept_id, "y": year, "w": week})
            db.execute(text("INSERT OR REPLACE INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Gluten',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
            db.execute(text("INSERT OR REPLACE INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Laktos',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
            db.execute(text("INSERT OR REPLACE INTO weekview_alt2_flags VALUES(:s,:d,:y,:w,1,:enabled)"), {"s": site_id, "d": dept_id, "y": year, "w": week, "enabled": alt2_enabled_monday})
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"
                )
            )
            db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,:enabled,1)"), {"s": site_id, "d": dept_id, "w": week, "enabled": alt2_enabled_monday})
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS department_menu_choices(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, meal TEXT NOT NULL DEFAULT 'lunch', selected_variant TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT, UNIQUE(tenant_id,site_id,department_id,year,week,weekday,meal))"
                )
            )
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,tenant_id,version) VALUES(:id,:name,1,0)"), {"id": site_id, "name": "Portal Site"})
            db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
            db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER, status TEXT NOT NULL DEFAULT 'draft')"))
            db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
            db.execute(text("DELETE FROM menu_variants WHERE menu_id=:menu_id"), {"menu_id": legacy_menu_id})
            db.execute(text("DELETE FROM menus WHERE id=:menu_id"), {"menu_id": legacy_menu_id})
            db.execute(text("DELETE FROM dishes WHERE id IN (501,502,503,504)"))
            db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(501,1,:n,NULL)"), {"n": legacy_alt1_name})
            db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(502,1,:n,NULL)"), {"n": legacy_alt2_name})
            db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(503,1,:n,NULL)"), {"n": legacy_dessert_name})
            db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(504,1,:n,NULL)"), {"n": legacy_dinner_name})
            db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year,status) VALUES(:id,1,:w,:y,'draft')"), {"id": legacy_menu_id, "w": week, "y": year})
            db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(:id,'mon','lunch','alt1',501)"), {"id": legacy_menu_id})
            db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(:id,'mon','lunch','alt2',502)"), {"id": legacy_menu_id})
            db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(:id,'mon','dessert','dessert',503)"), {"id": legacy_menu_id})
            db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(:id,'mon','dinner','dinner',504)"), {"id": legacy_menu_id})
            db.commit()
        finally:
            db.close()

    return _seed


@pytest.fixture
def seed_portal_menu_choice():
    def _seed(
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
        selected_variant: str,
        meal: str = "lunch",
    ) -> None:
        db = get_session()
        try:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS department_menu_choices(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, meal TEXT NOT NULL DEFAULT 'lunch', selected_variant TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT, UNIQUE(tenant_id,site_id,department_id,year,week,weekday,meal))"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES(:tenant_id, :site_id, :department_id, :year, :week, :weekday, :meal, :selected_variant, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "weekday": int(weekday),
                    "meal": str(meal),
                    "selected_variant": str(selected_variant).strip().lower(),
                },
            )
            db.commit()
        finally:
            db.close()

    return _seed


@pytest.fixture
def seed_canonical_builder_publication(app_session):
    def _seed(
        *,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str = "builder-menu-1",
        builder_version: int = 1,
        alt1_name: str = "Pannbiff med lök",
        alt1_menu_name: str | None = None,
        alt2_name: str = "Fiskgratäng",
        dessert_name: str = "Fruktsallad",
        dinner_name: str = "Kvällsgröt",
    ) -> CompositionService:
        with app_session.app_context():
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
            app_session.extensions["builder_menu_context_flow"] = menu_context_flow
            app_session.extensions["builder_flow"] = builder_flow

            composition_repository = builder_flow._composition_repository
            composition_service = CompositionService(repository=composition_repository)

            def _upsert_composition(composition_id: str, composition_name: str, *, use_custom_menu_name: bool = False, menu_name: str | None = None) -> None:
                if composition_service.get_composition(composition_id) is None:
                    composition_service.create_composition(
                        composition_id=composition_id,
                        composition_name=composition_name,
                        use_custom_menu_name=use_custom_menu_name,
                        menu_name=menu_name,
                    )
                else:
                    composition_service.update_composition_metadata(
                        composition_id,
                        composition_name=composition_name,
                        use_custom_menu_name=use_custom_menu_name,
                        menu_name=menu_name,
                    )

            _upsert_composition("builder-alt1", alt1_name, use_custom_menu_name=bool(alt1_menu_name), menu_name=alt1_menu_name)
            _upsert_composition("builder-alt2", alt2_name)
            _upsert_composition("builder-dessert", dessert_name)
            _upsert_composition("builder-dinner", dinner_name)

            if not any(str(menu.menu_id) == builder_menu_id for menu in menu_context_flow.list_menus()):
                menu_context_flow.create_menu(
                    menu_id=builder_menu_id,
                    site_id=site_id,
                    week_key=f"{year}-W{week:02d}",
                    version=builder_version,
                    status="published",
                )
                menu_context_flow.add_composition_menu_row(menu_id=builder_menu_id, day="monday", meal_slot="lunch_alt1", composition_id="builder-alt1")
                menu_context_flow.add_composition_menu_row(menu_id=builder_menu_id, day="monday", meal_slot="lunch_alt2", composition_id="builder-alt2")
                menu_context_flow.add_composition_menu_row(menu_id=builder_menu_id, day="monday", meal_slot="lunch_dessert", composition_id="builder-dessert")
                menu_context_flow.add_composition_menu_row(menu_id=builder_menu_id, day="monday", meal_slot="dinner_alt1", composition_id="builder-dinner")

            legacy_menu = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
            CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow).create_or_replace_link(
                tenant_id=1,
                site_id=site_id,
                year=year,
                week=week,
                builder_menu_id=builder_menu_id,
                source="manual",
            )
            MenuServiceDB().publish_menu(tenant_id=1, menu_id=legacy_menu.id)

            return composition_service

    return _seed
