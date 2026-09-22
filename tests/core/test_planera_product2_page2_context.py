from __future__ import annotations

import json
from datetime import date
import uuid

import pytest
from flask import current_app
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.commun_builder_projection import get_shadow_projection_reader
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
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.planera_product2_page2_context import (
    Product2Page2ContextError,
    build_product2_page2_planning_context,
)
from core.planera_v2.day_context_resolver import resolve_kommun_day_business_context
from core.ui_blueprint import _apply_builder_reader_weekview_overview
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.menu import InMemoryCompositionAliasRepository, MenuService


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


def _seed_site(app_session, *, site_id: str, tenant_id: int = 1) -> None:
    from core.db import get_new_session

    db = get_new_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tid, 0)"),
            {"id": site_id, "name": f"Site {site_id}", "tid": tenant_id},
        )
        db.commit()
    finally:
        db.close()


def _seed_department(*, site_id: str, name: str, resident_count: int = 10) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_requirement(site_id: str, name: str, requirement_key: str) -> int:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, :name, 'Övrigt', :requirement_key, 'atomic', 0)"
            ),
            {"site_id": site_id, "name": name, "requirement_key": requirement_key},
        )
        db.commit()
        row = db.execute(
            text("SELECT id FROM dietary_types WHERE requirement_key=:requirement_key AND site_id=:site_id"),
            {"requirement_key": requirement_key, "site_id": site_id},
        ).fetchone()
        assert row is not None
        return int(row[0])
    finally:
        db.close()


def _seed_requirement_group(*, department_id: str, requirement_ids: list[int], quantity: int, label: str) -> dict:
    return DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)


def _builder_day_name(service_date: date) -> str:
    return service_date.strftime("%A").lower()


def _seed_publication(
    *,
    app_session,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    builder_menu_version: int,
    day: str,
    meal_rows: list[tuple[str, str, int, str, str]],
) -> dict[str, str]:
    with app_session.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(
            menu_id=builder_menu_id,
            site_id=site_id,
            week_key=f"{year}-W{week:02d}",
            version=builder_menu_version,
            status="published",
        )
        for composition_id, composition_name, sort_order, meal_slot, row_day in meal_rows:
            composition_service.create_composition(
                composition_id=composition_id,
                composition_name=composition_name,
            )
            builder_flow.add_composition_menu_row(
                menu_id=builder_menu_id,
                day=row_day,
                meal_slot=meal_slot,
                composition_id=composition_id,
                sort_order=sort_order,
            )

        outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=builder_menu_version,
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
            builder_menu_version=builder_menu_version,
            source="manual",
            projection_snapshot_json=json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        return {
            str(row.variant_type): str(row.builder_menu_row_id)
            for row in outcome.projection.rows
            if str(row.day) == day and str(row.meal) == "lunch" and str(row.variant_type)
        }


def _seed_common_context(*, app_session, site_id: str, department_names: tuple[str, str] = ("Unit A", "Unit B")) -> tuple[date, dict, dict, dict, dict]:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    _seed_site(app_session, site_id=site_id)
    dept_a = _seed_department(site_id=site_id, name=department_names[0], resident_count=10)
    dept_b = _seed_department(site_id=site_id, name=department_names[1], resident_count=20)
    req_a = _seed_requirement(site_id, f"Requirement A {uuid.uuid4().hex[:8]}", f"req_a_{uuid.uuid4().hex[:8]}")
    req_b = _seed_requirement(site_id, f"Requirement B {uuid.uuid4().hex[:8]}", f"req_b_{uuid.uuid4().hex[:8]}")
    group_a = _seed_requirement_group(department_id=dept_a["id"], requirement_ids=[req_a], quantity=2, label="Group A")
    group_b = _seed_requirement_group(department_id=dept_b["id"], requirement_ids=[req_b], quantity=3, label="Group B")
    return service_date, dept_a, dept_b, group_a, group_b


def test_published_lunch_with_two_options_builds_context(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-{uuid.uuid4()}"
        service_date, dept_a, dept_b, group_a, group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        year, week, _weekday = service_date.isocalendar()
        row_ids = _seed_publication(
            app_session=app_session,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-page2",
            builder_menu_version=1,
            day=_builder_day_name(service_date),
            meal_rows=[
                ("row-alt1", "Alt 1 Dish", 10, "lunch_alt1", _builder_day_name(service_date)),
                ("row-alt2", "Alt 2 Dish", 20, "lunch_alt2", _builder_day_name(service_date)),
            ],
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_a["id"],
            year=year,
            week=week,
            weekday=service_date.isocalendar()[2],
            selected_alt="alt1",
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_b["id"],
            year=year,
            week=week,
            weekday=service_date.isocalendar()[2],
            selected_alt="alt2",
        )

        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal="lunch",
        )

        assert context.status == "ok"
        assert context.publication_identity is not None
        assert context.publication_identity.builder_menu_id == "builder-menu-page2"
        assert [option.option_id for option in context.options] == [row_ids["alt1"], row_ids["alt2"]]
        assert [option.variant_type for option in context.options] == ["alt1", "alt2"]
        destinations = {destination.destination_id: destination for destination in context.destinations}
        assert destinations[dept_a["id"]].baseline_quantity == 10
        assert destinations[dept_b["id"]].baseline_quantity == 20
        assert destinations[dept_a["id"]].selected_option_id == row_ids["alt1"]
        assert destinations[dept_b["id"]].selected_option_id == row_ids["alt2"]
        assert destinations[dept_a["id"]].choice_source == "explicit"
        assert destinations[dept_b["id"]].choice_source == "explicit"
        requirement_groups = {group.requirement_group_id: group for group in context.requirement_groups}
        assert requirement_groups[group_a["id"]].destination_id == dept_a["id"]
        assert requirement_groups[group_b["id"]].destination_id == dept_b["id"]
        assert requirement_groups[group_a["id"]].effective_quantity == 2
        assert requirement_groups[group_b["id"]].effective_quantity == 3
        assert requirement_groups[group_a["id"]].requirements[0].requirement_key is not None
        assert not hasattr(context, "review_state")


def test_missing_choice_stays_none_and_does_not_default_to_alt1(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-missing-{uuid.uuid4()}"
        service_date, dept_a, dept_b, group_a, group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        year, week, _weekday = service_date.isocalendar()
        row_ids = _seed_publication(
            app_session=app_session,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-page2-missing",
            builder_menu_version=1,
            day=_builder_day_name(service_date),
            meal_rows=[
                ("row-alt1", "Alt 1 Dish", 10, "lunch_alt1", _builder_day_name(service_date)),
                ("row-alt2", "Alt 2 Dish", 20, "lunch_alt2", _builder_day_name(service_date)),
            ],
        )

        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal="lunch",
        )

        destinations = {destination.destination_id: destination for destination in context.destinations}
        assert destinations[dept_a["id"]].selected_option_id is None
        assert destinations[dept_b["id"]].selected_option_id is None
        assert destinations[dept_a["id"]].choice_source == "none"
        assert destinations[dept_b["id"]].choice_source == "none"


def test_explicit_choice_referencing_absent_variant_fails_closed(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-bad-choice-{uuid.uuid4()}"
        service_date, dept_a, dept_b, _group_a, _group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        year, week, _weekday = service_date.isocalendar()
        row_ids = _seed_publication(
            app_session=app_session,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-page2-bad-choice",
            builder_menu_version=1,
            day=_builder_day_name(service_date),
            meal_rows=[
                ("row-alt1", "Alt 1 Dish", 10, "lunch_alt1", _builder_day_name(service_date)),
            ],
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dept_a["id"],
            year=year,
            week=week,
            weekday=service_date.isocalendar()[2],
            selected_alt="alt2",
        )

        with pytest.raises(Product2Page2ContextError, match="selected_variant_missing_from_publication:alt2"):
            build_product2_page2_planning_context(
                tenant_id=1,
                site_id=site_id,
                service_date=service_date,
                meal="lunch",
            )


def test_requirement_group_effective_quantity_uses_override_and_excludes_zero(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-override-{uuid.uuid4()}"
        service_date, dept_a, dept_b, group_a, group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        year, week, _weekday = service_date.isocalendar()
        _seed_publication(
            app_session=app_session,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-page2-override",
            builder_menu_version=1,
            day=_builder_day_name(service_date),
            meal_rows=[
                ("row-alt1", "Alt 1 Dish", 10, "lunch_alt1", _builder_day_name(service_date)),
                ("row-alt2", "Alt 2 Dish", 20, "lunch_alt2", _builder_day_name(service_date)),
            ],
        )

        overrides = DepartmentRequirementGroupServiceOverridesRepo()
        overrides.set_override(group_a["id"], service_date, "lunch", 4)
        overrides.set_override(group_b["id"], service_date, "lunch", 0)

        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal="lunch",
        )

        requirement_groups = {group.requirement_group_id: group for group in context.requirement_groups}
        assert requirement_groups[group_a["id"]].effective_quantity == 4
        assert group_b["id"] not in requirement_groups

        overrides.set_override(group_a["id"], date(2026, 9, 8), "dinner", 9)
        assert overrides.resolve_effective_quantity(group_a["id"], service_date, "lunch") == 4
        assert overrides.resolve_effective_quantity(group_a["id"], service_date, "dinner") == 9


def test_no_publication_returns_explicit_no_publication_state(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-empty-{uuid.uuid4()}"
        service_date, dept_a, dept_b, _group_a, _group_b = _seed_common_context(app_session=app_session, site_id=site_id)

        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal="lunch",
        )

        assert context.status == "no_publication"
        assert context.publication_identity is None
        assert context.options == ()


def test_cross_tenant_site_fails_closed(app_session, monkeypatch) -> None:
    with app_session.app_context():
        site_id = f"site-page2-cross-{uuid.uuid4()}"
        service_date, _dept_a, _dept_b, _group_a, _group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        monkeypatch.setattr("core.planera_v2.day_context_resolver.get_site_tenant", lambda _site_id: 2)

        with pytest.raises(Exception, match="site_not_owned"):
            build_product2_page2_planning_context(
                tenant_id=1,
                site_id=site_id,
                service_date=service_date,
                meal="lunch",
            )


def test_three_published_options_remain_collection_shaped(app_session) -> None:
    with app_session.app_context():
        site_id = f"site-page2-three-{uuid.uuid4()}"
        service_date, dept_a, dept_b, _group_a, _group_b = _seed_common_context(app_session=app_session, site_id=site_id)
        year, week, _weekday = service_date.isocalendar()
        row_ids = _seed_publication(
            app_session=app_session,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-page2-three",
            builder_menu_version=1,
            day=_builder_day_name(service_date),
            meal_rows=[
                ("row-main", "Main Dish", 5, "lunch_main", _builder_day_name(service_date)),
                ("row-alt1", "Alt 1 Dish", 10, "lunch_alt1", _builder_day_name(service_date)),
                ("row-alt2", "Alt 2 Dish", 20, "lunch_alt2", _builder_day_name(service_date)),
            ],
        )

        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=site_id,
            service_date=service_date,
            meal="lunch",
        )

        assert len(context.options) == 3
        assert [option.option_id for option in context.options] == [row_ids["main"], row_ids["alt1"], row_ids["alt2"]]
        assert [option.variant_type for option in context.options] == ["main", "alt1", "alt2"]
        assert not hasattr(context, "alt1_quantity")
        assert not hasattr(context, "alt2_quantity")
