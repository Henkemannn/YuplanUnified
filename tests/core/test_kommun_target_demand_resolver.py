from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import pytest
from flask import current_app
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.commun_builder_projection import get_shadow_projection_reader
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
from core.department_menu_choice_repo import MenuChoiceRepo
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planera_product2_page2_context import Product2Page2ContextError, resolve_product2_page2_target
from core.planera_v2.adapters.kommun_target_demand import (
    resolve_kommun_target_demand,
)
from core.planera_v2.day_context_resolver import resolve_kommun_day_business_context


@dataclass
class _DemandTestState:
    site_ids: set[str] = field(default_factory=set)


_DEMAND_TEST_STATE: _DemandTestState | None = None


def _state() -> _DemandTestState:
    assert _DEMAND_TEST_STATE is not None
    return _DEMAND_TEST_STATE


def _cleanup_state(state: _DemandTestState) -> None:
    from core.db import get_session

    db = get_session()
    try:
        for site_id in sorted(state.site_ids):
            db.execute(text("DELETE FROM commun_builder_publication_pins WHERE site_id = :site_id"), {"site_id": site_id})
            db.execute(text("DELETE FROM department_menu_choices WHERE site_id = :site_id"), {"site_id": site_id})
            db.execute(text("DELETE FROM departments WHERE site_id = :site_id"), {"site_id": site_id})
            db.execute(text("DELETE FROM sites WHERE id = :site_id"), {"site_id": site_id})
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _demand_hygiene(app_session):
    global _DEMAND_TEST_STATE
    state = _DemandTestState()
    _DEMAND_TEST_STATE = state
    extension_snapshot = {
        key: (key in app_session.extensions, app_session.extensions.get(key))
        for key in ("builder_menu_context_flow", "builder_flow")
    }
    try:
        yield state
    finally:
        _cleanup_state(state)
        for key, (existed, value) in extension_snapshot.items():
            if existed:
                app_session.extensions[key] = value
            else:
                app_session.extensions.pop(key, None)
        _DEMAND_TEST_STATE = None


def _build_builder_menu_context_flow() -> tuple[BuilderMenuContextFlow, CompositionService]:
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


def _seed_site(site_name: str, tenant_id: int = 1) -> str:
    if tenant_id != 1:
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:id, :name, 1)"),
                {"id": tenant_id, "name": f"Tenant {tenant_id}"},
            )
            db.commit()
        finally:
            db.close()
    site, _ = SitesRepo().create_site(name=site_name, tenant_id=tenant_id)
    _state().site_ids.add(site["id"])
    return site["id"]


def _seed_department(*, site_id: str, name: str, resident_count: int) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_publication(*, site_id: str, builder_menu_id: str, service_date: date, meal_rows: list[tuple[str, str, int, str, str]]) -> dict[tuple[str, str, str], str]:
    year, week, _weekday = service_date.isocalendar()
    builder_flow, composition_service = _build_builder_menu_context_flow()
    current_app.extensions["builder_menu_context_flow"] = builder_flow
    current_app.extensions["builder_flow"] = builder_flow
    builder_flow.create_menu(
        menu_id=builder_menu_id,
        site_id=site_id,
        week_key=f"{year}-W{week:02d}",
        version=1,
        status="published",
    )
    for composition_id, composition_name, _sort_order, meal_slot, row_day in meal_rows:
        composition_service.create_composition(composition_id=composition_id, composition_name=composition_name)
        builder_flow.add_composition_menu_row(
            menu_id=builder_menu_id,
            day=row_day,
            meal_slot=meal_slot,
            composition_id=composition_id,
            sort_order=_sort_order,
        )

    outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
        tenant_id=1,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=builder_menu_id,
        builder_menu_version=1,
    )
    assert outcome.status == "ok"
    assert outcome.projection is not None
    snapshot = {
        "schema_version": 1,
        "tenant_id": int(outcome.projection.tenant_id),
        "site_id": str(outcome.projection.site_id),
        "year": int(outcome.projection.year),
        "week": int(outcome.projection.week),
        "builder_menu_id": str(outcome.projection.builder_menu_id),
        "builder_menu_version": int(outcome.projection.builder_menu_version),
        "builder_status": str(outcome.projection.builder_status),
        "projection_version": int(outcome.projection.projection_version),
        "source": str(outcome.projection.source),
        "rows": [
            {
                "day": row.day,
                "meal": row.meal,
                "variant_type": row.variant_type,
                "sort_order": int(row.sort_order),
                "builder_menu_row_id": row.builder_menu_row_id,
                "selection_group_id": row.selection_group_id,
                "composition_id": row.composition_id,
                "resolved": bool(row.resolved),
                "text": row.text,
                "unresolved_text": row.unresolved_text,
                "error": row.error,
            }
            for row in outcome.projection.rows
        ],
    }
    CommunBuilderPublicationRepository().upsert_publication(
        tenant_id=1,
        site_id=site_id,
        year=year,
        week=week,
        legacy_menu_id=None,
        builder_menu_id=builder_menu_id,
        builder_menu_version=1,
        source="manual",
        projection_snapshot_json=json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
    )
    return {
        (str(row.day), str(row.meal), str(row.variant_type)): str(row.builder_menu_row_id)
        for row in outcome.projection.rows
    }


def test_lunch_alt_targets_distinguish_positive_zero_and_unresolved(app_session):
    with app_session.app_context():
        service_date = date(2026, 10, 12)
        site_id = _seed_site("Demand Site")
        dept_a = _seed_department(site_id=site_id, name="Alpha", resident_count=12)
        dept_b = _seed_department(site_id=site_id, name="Beta", resident_count=10)
        dept_c = _seed_department(site_id=site_id, name="Gamma", resident_count=0)
        year, week, weekday = service_date.isocalendar()
        publication_row_ids = _seed_publication(
            site_id=site_id,
            builder_menu_id="builder-menu-demand-1",
            service_date=service_date,
            meal_rows=[
                ("cmp-a1", "Alt 1", 10, "lunch_alt1", "monday"),
                ("cmp-a2", "Alt 2", 20, "lunch_alt2", "monday"),
                ("cmp-dessert", "Glassbomb", 30, "lunch_dessert", "monday"),
                ("cmp-dinner", "Kvällsrätt", 40, "dinner_main", "monday"),
            ],
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_a["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt1",
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_b["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt2",
        )
        context = resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal_labels={"lunch": "Fika", "dinner": "Andra sittningen"},
        )
        alt1_target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("monday", "lunch", "alt1")],
            meal="lunch",
        )
        alt2_target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("monday", "lunch", "alt2")],
            meal="lunch",
        )
        alt1_result = resolve_kommun_target_demand(context=context, target=alt1_target)
        alt2_result = resolve_kommun_target_demand(context=context, target=alt2_target)

        assert alt1_result.builder_menu_row_id == publication_row_ids[("monday", "lunch", "alt1")]
        assert alt2_result.builder_menu_row_id == publication_row_ids[("monday", "lunch", "alt2")]

        alt1_by_destination = {row.destination_id: row for row in alt1_result.destination_demands}
        alt2_by_destination = {row.destination_id: row for row in alt2_result.destination_demands}

        assert alt1_by_destination[dept_a["id"]].resolved_quantity == 12
        assert alt1_by_destination[dept_a["id"]].resolution_state == "resolved_positive"
        assert alt1_by_destination[dept_b["id"]].resolved_quantity == 0
        assert alt1_by_destination[dept_b["id"]].resolution_state == "resolved_zero"
        assert alt1_by_destination[dept_c["id"]].resolved_quantity is None
        assert alt1_by_destination[dept_c["id"]].resolution_state == "unresolved"
        assert alt1_by_destination[dept_c["id"]].unresolved_reason == "menu_choice_missing"

        assert alt2_by_destination[dept_b["id"]].resolved_quantity == 10
        assert alt2_by_destination[dept_b["id"]].resolution_state == "resolved_positive"
        assert alt2_by_destination[dept_a["id"]].resolved_quantity == 0
        assert alt2_by_destination[dept_a["id"]].resolution_state == "resolved_zero"
        assert alt2_by_destination[dept_c["id"]].resolved_quantity is None
        assert alt2_by_destination[dept_c["id"]].resolution_state == "unresolved"


def test_dessert_and_dinner_targets_use_existing_baselines(app_session):
    with app_session.app_context():
        service_date = date(2026, 10, 12)
        site_id = _seed_site("Demand Dessert Site")
        dept_a = _seed_department(site_id=site_id, name="Alpha", resident_count=12)
        dept_b = _seed_department(site_id=site_id, name="Beta", resident_count=10)
        dept_c = _seed_department(site_id=site_id, name="Gamma", resident_count=0)
        year, week, weekday = service_date.isocalendar()
        publication_row_ids = _seed_publication(
            site_id=site_id,
            builder_menu_id="builder-menu-demand-2",
            service_date=service_date,
            meal_rows=[
                ("cmp-a1", "Alt 1", 10, "lunch_alt1", "monday"),
                ("cmp-a2", "Alt 2", 20, "lunch_alt2", "monday"),
                ("cmp-dessert", "Glassbomb", 30, "lunch_dessert", "monday"),
                ("cmp-dinner", "Kvällsrätt", 40, "dinner_main", "monday"),
            ],
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_a["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt1",
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_b["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt2",
        )
        context = resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
        )
        dessert_target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("monday", "lunch", "dessert")],
            meal="lunch",
        )
        dinner_target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("monday", "dinner", "main")],
            meal="dinner",
        )
        dessert_result = resolve_kommun_target_demand(context=context, target=dessert_target)
        dinner_result = resolve_kommun_target_demand(context=context, target=dinner_target)

        dessert_by_destination = {row.destination_id: row for row in dessert_result.destination_demands}
        dinner_by_destination = {row.destination_id: row for row in dinner_result.destination_demands}

        assert dessert_target.meal == "lunch"
        assert dessert_target.variant_type == "dessert"
        assert dessert_by_destination[dept_a["id"]].resolved_quantity == 12
        assert dessert_by_destination[dept_b["id"]].resolved_quantity == 10
        assert dessert_by_destination[dept_c["id"]].resolved_quantity == 0
        assert dessert_by_destination[dept_c["id"]].resolution_state == "resolved_zero"

        assert dinner_target.meal == "dinner"
        assert dinner_by_destination[dept_a["id"]].resolved_quantity == 12
        assert dinner_by_destination[dept_b["id"]].resolved_quantity == 10
        assert dinner_by_destination[dept_c["id"]].resolved_quantity == 0
        assert dinner_by_destination[dept_c["id"]].resolution_state == "resolved_zero"


def test_service_labels_do_not_change_target_demand(app_session):
    with app_session.app_context():
        service_date = date(2026, 10, 12)
        site_id = _seed_site("Label Safety Site")
        dept_a = _seed_department(site_id=site_id, name="Alpha", resident_count=12)
        dept_b = _seed_department(site_id=site_id, name="Beta", resident_count=10)
        year, week, weekday = service_date.isocalendar()
        publication_row_ids = _seed_publication(
            site_id=site_id,
            builder_menu_id="builder-menu-demand-3",
            service_date=service_date,
            meal_rows=[
                ("cmp-a1", "Alt 1", 10, "lunch_alt1", "monday"),
                ("cmp-a2", "Alt 2", 20, "lunch_alt2", "monday"),
            ],
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_a["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt1",
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_b["id"],
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="alt2",
        )
        canonical_context = resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
        )
        custom_context = resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal_labels={"lunch": "Fika", "dinner": "Andra sittningen"},
        )
        target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("monday", "lunch", "alt1")],
            meal="lunch",
        )

        canonical_result = resolve_kommun_target_demand(context=canonical_context, target=target)
        custom_result = resolve_kommun_target_demand(context=custom_context, target=target)

        assert canonical_result == custom_result


def test_sunday_has_no_alt2_target(app_session):
    with app_session.app_context():
        service_date = date(2026, 10, 18)
        site_id = _seed_site("Sunday Site")
        _seed_department(site_id=site_id, name="Alpha", resident_count=12)
        _seed_department(site_id=site_id, name="Beta", resident_count=10)
        _seed_department(site_id=site_id, name="Gamma", resident_count=0)
        publication_row_ids = _seed_publication(
            site_id=site_id,
            builder_menu_id="builder-menu-demand-4",
            service_date=service_date,
            meal_rows=[
                ("cmp-sun-a1", "Sunday Alt 1", 10, "lunch_alt1", "sunday"),
                ("cmp-sun-dessert", "Sunday Dessert", 20, "lunch_dessert", "sunday"),
                ("cmp-sun-dinner", "Sunday Dinner", 30, "dinner_main", "sunday"),
            ],
        )

        assert ("sunday", "lunch", "alt2") not in publication_row_ids
        sunday_context = resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
        )
        alt1_target = resolve_product2_page2_target(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            option_id=publication_row_ids[("sunday", "lunch", "alt1")],
            meal="lunch",
        )
        alt1_result = resolve_kommun_target_demand(context=sunday_context, target=alt1_target)
        assert alt1_result.builder_menu_row_id == publication_row_ids[("sunday", "lunch", "alt1")]
        assert alt1_result.destination_demands[0].resolution_state in {"resolved_positive", "resolved_zero", "unresolved"}


def test_nonexistent_publication_target_fails_closed(app_session):
    with app_session.app_context():
        service_date = date(2026, 10, 12)
        site_id = _seed_site("Missing Target Site")
        _seed_department(site_id=site_id, name="Alpha", resident_count=12)
        _seed_department(site_id=site_id, name="Beta", resident_count=10)
        _seed_publication(
            site_id=site_id,
            builder_menu_id="builder-menu-demand-5",
            service_date=service_date,
            meal_rows=[
                ("cmp-a1", "Alt 1", 10, "lunch_alt1", "monday"),
                ("cmp-dessert", "Glassbomb", 20, "lunch_dessert", "monday"),
            ],
        )

        with pytest.raises(Product2Page2ContextError, match="target_not_published"):
            resolve_product2_page2_target(
                tenant_id=1,
                site_id=site_id,
                service_date=service_date,
                option_id="does-not-exist",
                meal="lunch",
            )
