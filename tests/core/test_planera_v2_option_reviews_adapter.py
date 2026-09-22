from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import uuid
from types import SimpleNamespace

import pytest
from flask import current_app
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
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
from core.db import get_new_session, get_session
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planera_v2.acceptance import validate_plan_request_for_production
from core.planera_v2.engine import compute_plan
from core.planera_v2.adapters.kommun_from_option_reviews import (
    KommunOptionReviewPlanningError,
    build_planning_slice_from_option_review,
)
from core.planera_v2.shadow import run_plan_request_in_production_shadow
from core.planning_option_review import (
    ADAPTATION_REQUIRED,
    NO_ADAPTATION_REQUIRED,
    PlanningOptionReviewService,
)


@dataclass
class _OptionReviewAdapterState:
    site_ids: set[str] = field(default_factory=set)
    tenant_ids: set[int] = field(default_factory=set)


_STATE: _OptionReviewAdapterState | None = None


def _state() -> _OptionReviewAdapterState:
    assert _STATE is not None
    return _STATE


@pytest.fixture(autouse=True)
def _option_review_adapter_hygiene(app_session):
    global _STATE
    _STATE = _OptionReviewAdapterState()
    extension_snapshot = {
        key: (key in app_session.extensions, app_session.extensions.get(key))
        for key in ("builder_menu_context_flow", "builder_flow")
    }
    try:
        yield
    finally:
        db = get_session()
        try:
            for site_id in sorted(_state().site_ids):
                db.execute(text("DELETE FROM commun_builder_publication_pins WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_menu_choices WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_service_overrides WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_requirements WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id)"), {"site_id": site_id})
                db.execute(text("DELETE FROM dietary_types WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM departments WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM sites WHERE id = :site_id"), {"site_id": site_id})
            db.execute(text("DELETE FROM planning_option_review_decisions"))
            db.execute(text("DELETE FROM planning_option_reviews"))
            for tenant_id in sorted(_state().tenant_ids):
                if int(tenant_id) == 1:
                    continue
                db.execute(text("DELETE FROM tenants WHERE id = :tenant_id"), {"tenant_id": int(tenant_id)})
            db.commit()
        finally:
            db.close()
        for key, (existed, value) in extension_snapshot.items():
            if existed:
                app_session.extensions[key] = value
            else:
                app_session.extensions.pop(key, None)
        _STATE = None


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
        alias_repository=InMemoryCompositionAliasRepository(),
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return menu_context_flow, CompositionService(repository=composition_repository)


def _seed_site(*, site_name: str, tenant_id: int = 1) -> str:
    db = get_new_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:id, :name, 1)"), {"id": tenant_id, "name": f"Tenant {tenant_id}"})
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"),
            {"id": site_name, "name": f"Site {site_name}", "tenant_id": tenant_id},
        )
        db.commit()
    finally:
        db.close()
    _state().tenant_ids.add(int(tenant_id))
    _state().site_ids.add(site_name)
    return site_name


def _seed_department(site_id: str, name: str, resident_count: int) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_requirement(site_id: str, name: str, requirement_key: str) -> int:
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


def _seed_group(*, department_id: str, requirement_ids: list[int], quantity: int, label: str) -> dict:
    return DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)


def _seed_publication(
    app_session,
    *,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    day: str,
    variant_types: tuple[str, ...] = ("alt1", "alt2"),
) -> dict[str, str]:
    with app_session.app_context():
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
        composition_names = {
            "alt1": ("comp-alt1", "Fläskkarré"),
            "alt2": ("comp-alt2", "Kokt torsk"),
        }
        for variant_type in variant_types:
            composition_id, composition_name = composition_names.get(
                variant_type,
                (f"comp-{variant_type}", variant_type),
            )
            composition_service.create_composition(composition_id=composition_id, composition_name=composition_name)
            builder_flow.add_composition_menu_row(
                menu_id=builder_menu_id,
                menu_detail_id=f"detail-{variant_type}",
                day=day,
                meal_slot=f"lunch_{variant_type}",
                composition_id=composition_id,
                sort_order=10 if variant_type == "alt1" else 20,
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
            projection_snapshot_json=__import__("json").dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        return {
            str(row.variant_type): str(row.builder_menu_row_id)
            for row in outcome.projection.rows
            if str(row.day) == day and str(row.meal) == "lunch"
        }


def _build_publication_snapshot(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    day: str,
    builder_menu_id: str,
    builder_menu_version: int,
    variant_types: tuple[str, ...] = ("alt1", "alt2"),
) -> dict[str, str]:
    menu_context_flow, composition_service = _build_builder_menu_context_flow()
    current_app.extensions["builder_menu_context_flow"] = menu_context_flow
    current_app.extensions["builder_flow"] = menu_context_flow
    menu_context_flow.create_menu(
        menu_id=builder_menu_id,
        site_id=site_id,
        week_key=f"{year}-W{week:02d}",
        version=builder_menu_version,
        status="published",
    )
    composition_names = {
        "alt1": ("comp-alt1", "Fläskkarré"),
        "alt2": ("comp-alt2", "Kokt torsk"),
    }
    for variant_type in variant_types:
        composition_id, composition_name = composition_names.get(
            variant_type,
            (f"comp-{variant_type}", variant_type),
        )
        composition_service.create_composition(composition_id=composition_id, composition_name=composition_name)
        menu_context_flow.add_composition_menu_row(
            menu_id=builder_menu_id,
            day=day,
            meal_slot=f"lunch_{variant_type}",
            composition_id=composition_id,
            sort_order=10 if variant_type == "alt1" else 20,
        )
    outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
        tenant_id=tenant_id,
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
        tenant_id=tenant_id,
        site_id=site_id,
        year=year,
        week=week,
        legacy_menu_id=None,
        builder_menu_id=builder_menu_id,
        builder_menu_version=builder_menu_version,
        source="manual",
        projection_snapshot_json=__import__("json").dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
    )
    return {
        str(row.variant_type): str(row.builder_menu_row_id)
        for row in outcome.projection.rows
        if str(row.day) == day and str(row.meal) == "lunch"
    }


def _review_payload(destination_id: str, requirement_group_id: str, decision: str) -> dict[str, str]:
    return {
        "destination_id": destination_id,
        "requirement_group_id": requirement_group_id,
        "decision": decision,
    }


def _build_scenario(
    app_session,
    *,
    include_groups: bool = True,
    include_third_destination: bool = False,
    dept_b_choice: str = "alt2",
    assign_choices: bool = True,
) -> tuple:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = f"option-review-{uuid.uuid4()}"
    _seed_site(site_name=site_id)
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=18)
    dept_b = _seed_department(site_id, "Avdelning B", resident_count=12)
    dept_c = _seed_department(site_id, "Avdelning C", resident_count=9) if include_third_destination else None
    group_a = group_b = group_c = None
    if include_groups:
        req_a = _seed_requirement(site_id, f"Glutenfri {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
        req_b = _seed_requirement(site_id, f"Vegetarisk {uuid.uuid4().hex[:8]}", f"req_veg_{uuid.uuid4().hex[:8]}")
        group_a = _seed_group(department_id=dept_a["id"], requirement_ids=[req_a], quantity=3, label="Glutenfri")
        group_b = _seed_group(department_id=dept_b["id"], requirement_ids=[req_b], quantity=4, label="Vegetarisk")
        if dept_c is not None:
            req_c = _seed_requirement(site_id, f"Laktos {uuid.uuid4().hex[:8]}", f"req_lakt_{uuid.uuid4().hex[:8]}")
            group_c = _seed_group(department_id=dept_c["id"], requirement_ids=[req_c], quantity=2, label="Laktos")
    option_ids = _seed_publication(
        app_session,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
        day=service_date.strftime("%A").lower(),
    )
    if assign_choices:
        MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt1")
        MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_b["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt=dept_b_choice)
    return service_date, site_id, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids


def _save_review(site_id: str, service_date: date, option_id: str, decisions: list[dict[str, str]]) -> None:
    PlanningOptionReviewService().save_option_review(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_id,
        decisions=decisions,
        reviewed_by_user_id=1,
    )


def _build_slice(site_id: str, service_date: date, option_id: str, *, context: dict[str, object] | None = None):
    return build_planning_slice_from_option_review(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal_key="lunch",
        option_id=option_id,
        context=context,
    )


def test_unreviewed_option_fails_closed(app_session) -> None:
    service_date, site_id, _dept_a, _dept_b, _dept_c, _group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=False)

    with pytest.raises(KommunOptionReviewPlanningError, match="option_review_required"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_stale_review_fails_closed(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], NO_ADAPTATION_REQUIRED)],
    )
    DepartmentRequirementGroupServiceOverridesRepo().set_override(group_a["id"], service_date, "lunch", 0)

    with pytest.raises(KommunOptionReviewPlanningError, match="option_review_stale"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_reviewed_no_deviations_builds_baseline_only_slice(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], NO_ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])

    assert slice_.baseline == 18
    assert [unit.unit_id for unit in slice_.units] == [dept_a["id"]]
    assert slice_.deviations == ()


def test_one_adaptation_required_group_emits_one_deviation(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])

    assert len(slice_.deviations) == 1
    assert slice_.deviations[0].quantity == 3
    assert slice_.deviations[0].unit_id == dept_a["id"]
    assert slice_.deviations[0].category_keys and len(slice_.deviations[0].category_keys) == 1


def test_no_adaptation_required_group_emits_no_deviation(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], NO_ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert slice_.deviations == ()


def test_mixed_yes_no_review_only_emits_yes_groups(app_session) -> None:
    service_date, site_id, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, dept_b_choice="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [
            _review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED),
            _review_payload(dept_b["id"], group_b["id"], NO_ADAPTATION_REQUIRED),
        ],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])

    assert len(slice_.deviations) == 1
    assert slice_.deviations[0].unit_id == dept_a["id"]
    assert slice_.deviations[0].quantity == 3


def test_multi_requirement_cohort_emits_one_deviation_and_counts_once(app_session) -> None:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = _seed_site(site_name=f"option-review-multi-{uuid.uuid4()}")
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=10)
    req_gluten = _seed_requirement(site_id, f"Gluten {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
    req_lactose = _seed_requirement(site_id, f"Laktos {uuid.uuid4().hex[:8]}", f"req_lakt_{uuid.uuid4().hex[:8]}")
    group = _seed_group(department_id=dept_a["id"], requirement_ids=[req_gluten, req_lactose], quantity=2, label="Gluten + Lactose")
    option_ids = _seed_publication(
        app_session,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
        day=service_date.strftime("%A").lower(),
    )
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group["id"], ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert len(slice_.deviations) == 1
    assert slice_.deviations[0].quantity == 2
    assert slice_.deviations[0].category_keys == sorted(slice_.deviations[0].category_keys)
    assert slice_.context["requirement_group_refs"][0]["quantity"] == 2


def test_quantity_change_after_review_emits_current_quantity_and_review_stays_current(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )
    DepartmentRequirementGroupServiceOverridesRepo().set_override(group_a["id"], service_date, "lunch", 4)
    review_state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert review_state.review_is_stale is False

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert slice_.deviations[0].quantity == 4


def test_cohort_total_exceeding_destination_baseline_fails_closed(app_session) -> None:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = _seed_site(site_name=f"option-review-overflow-{uuid.uuid4()}")
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=5)
    req_gluten = _seed_requirement(site_id, f"Gluten {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
    req_veg = _seed_requirement(site_id, f"Vegetarisk {uuid.uuid4().hex[:8]}", f"req_veg_{uuid.uuid4().hex[:8]}")
    req_lakt = _seed_requirement(site_id, f"Laktos {uuid.uuid4().hex[:8]}", f"req_lakt_{uuid.uuid4().hex[:8]}")
    group_a = _seed_group(department_id=dept_a["id"], requirement_ids=[req_gluten], quantity=2, label="Gluten")
    group_b = _seed_group(department_id=dept_a["id"], requirement_ids=[req_veg], quantity=3, label="Vegetarian")
    group_c = _seed_group(department_id=dept_a["id"], requirement_ids=[req_gluten, req_lakt], quantity=1, label="Gluten + Lactose")
    option_ids = _seed_publication(
        app_session,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
        day=service_date.strftime("%A").lower(),
    )
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [
            _review_payload(dept_a["id"], group_a["id"], NO_ADAPTATION_REQUIRED),
            _review_payload(dept_a["id"], group_b["id"], NO_ADAPTATION_REQUIRED),
            _review_payload(dept_a["id"], group_c["id"], NO_ADAPTATION_REQUIRED),
        ],
    )

    with pytest.raises(KommunOptionReviewPlanningError, match="cohort_quantity_exceeds_baseline"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_zero_requirement_groups_builds_baseline_only_slice(app_session) -> None:
    service_date, site_id, dept_a, dept_b, _dept_c, _group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=False, dept_b_choice="alt1")
    _save_review(site_id, service_date, option_ids["alt1"], [])

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert len(slice_.units) == 2
    assert slice_.deviations == ()


def test_zero_assigned_destinations_produces_valid_zero_slice(app_session) -> None:
    service_date, site_id, dept_a, dept_b, dept_c, _group_a, _group_b, _group_c, option_ids = _build_scenario(
        app_session,
        include_groups=False,
        dept_b_choice="alt2",
        assign_choices=False,
    )
    _save_review(site_id, service_date, option_ids["alt1"], [])

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert slice_.baseline == 0
    assert slice_.units == ()
    assert slice_.deviations == ()


def test_unassigned_destination_is_excluded(app_session) -> None:
    service_date, site_id, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=True, dept_b_choice="alt2")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    assert dept_b["id"] not in [unit.unit_id for unit in slice_.units]
    if dept_c is not None:
        assert dept_c["id"] not in [unit.unit_id for unit in slice_.units]


def test_wrong_option_decision_cannot_leak_into_slice(app_session) -> None:
    service_date, site_id, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, dept_b_choice="alt2")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )
    db = get_session()
    try:
        review_row = db.execute(text("SELECT id FROM planning_option_reviews ORDER BY id DESC LIMIT 1")).fetchone()
        assert review_row is not None
        db.execute(
            text(
                "INSERT INTO planning_option_review_decisions(review_id, tenant_id, destination_id, requirement_group_id, decision, created_at, updated_at) VALUES (:review_id, 1, :destination_id, :requirement_group_id, 'ADAPTATION_REQUIRED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"review_id": int(review_row[0]), "destination_id": dept_b["id"], "requirement_group_id": group_b["id"]},
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(KommunOptionReviewPlanningError, match="irrelevant_decision"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_missing_requirement_key_fails_closed(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )
    db = get_session()
    try:
        db.execute(text("UPDATE dietary_types SET requirement_key = NULL WHERE id IN (SELECT dietary_type_id FROM department_requirement_group_requirements WHERE group_id = :group_id LIMIT 1)"), {"group_id": group_a["id"]})
        db.commit()
    finally:
        db.close()

    with pytest.raises(KommunOptionReviewPlanningError, match="requirement_key_missing"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_missing_current_decision_fails_closed(app_session) -> None:
    service_date, site_id, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, dept_b_choice="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [
            _review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED),
            _review_payload(dept_b["id"], group_b["id"], NO_ADAPTATION_REQUIRED),
        ],
    )
    db = get_session()
    try:
        db.execute(
            text(
                "DELETE FROM planning_option_review_decisions WHERE destination_id = :destination_id AND requirement_group_id = :requirement_group_id"
            ),
            {"destination_id": dept_b["id"], "requirement_group_id": group_b["id"]},
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(KommunOptionReviewPlanningError, match="missing_decision"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_duplicate_decision_key_fails_closed(app_session, monkeypatch) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )

    fake_review_state = SimpleNamespace(
        review_is_stale=False,
        review_id=1,
        completed_at=service_date,
        review_state="REVIEWED_WITH_DEVIATIONS",
        review_basis_hash="fake",
        decisions=[
            SimpleNamespace(destination_id=dept_a["id"], requirement_group_id=group_a["id"], decision=ADAPTATION_REQUIRED),
            SimpleNamespace(destination_id=dept_a["id"], requirement_group_id=group_a["id"], decision=ADAPTATION_REQUIRED),
        ],
    )

    monkeypatch.setattr(
        "core.planera_v2.adapters.kommun_from_option_reviews.PlanningOptionReviewService.get_option_review_state",
        lambda self, **kwargs: fake_review_state,
    )

    with pytest.raises(KommunOptionReviewPlanningError, match="duplicate_decision"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_invalid_requirement_semantics_fails_closed(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )
    db = get_session()
    try:
        db.execute(
            text("UPDATE dietary_types SET semantics = 'composite' WHERE id IN (SELECT dietary_type_id FROM department_requirement_group_requirements WHERE group_id = :group_id LIMIT 1)"),
            {"group_id": group_a["id"]},
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(KommunOptionReviewPlanningError, match="requirement_semantics_invalid"):
        _build_slice(site_id, service_date, option_ids["alt1"])


def test_option_no_longer_published_fails_closed(app_session) -> None:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = _seed_site(site_name=f"option-review-republish-{uuid.uuid4()}")
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=18)
    req_a = _seed_requirement(site_id, f"Glutenfri {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
    group_a = _seed_group(department_id=dept_a["id"], requirement_ids=[req_a], quantity=3, label="Glutenfri")
    with app_session.app_context():
        option_ids_v1 = _build_publication_snapshot(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            day=service_date.strftime("%A").lower(),
            builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
            builder_menu_version=1,
            variant_types=("alt1", "alt2"),
        )
        MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt1")
        _save_review(
            site_id,
            service_date,
            option_ids_v1["alt1"],
            [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
        )

        _build_publication_snapshot(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            day=service_date.strftime("%A").lower(),
            builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
            builder_menu_version=2,
            variant_types=("alt2",),
        )
        MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt2")

    with pytest.raises(KommunOptionReviewPlanningError, match="option_not_published"):
        _build_slice(site_id, service_date, option_ids_v1["alt1"])


def test_exact_engine_result_from_review_slice(app_session) -> None:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = _seed_site(site_name=f"option-review-engine-{uuid.uuid4()}")
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=18)
    gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
    veg_key = f"req_veg_{uuid.uuid4().hex[:8]}"
    req_gluten = _seed_requirement(site_id, f"Gluten {uuid.uuid4().hex[:8]}", gluten_key)
    req_veg = _seed_requirement(site_id, f"Vegetarisk {uuid.uuid4().hex[:8]}", veg_key)
    group_gluten = _seed_group(department_id=dept_a["id"], requirement_ids=[req_gluten], quantity=3, label="Gluten")
    group_veg = _seed_group(department_id=dept_a["id"], requirement_ids=[req_veg], quantity=4, label="Vegetarian")
    option_ids = _seed_publication(
        app_session,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
        day=service_date.strftime("%A").lower(),
    )
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=service_date.isocalendar()[2], selected_alt="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [
            _review_payload(dept_a["id"], group_gluten["id"], ADAPTATION_REQUIRED),
            _review_payload(dept_a["id"], group_veg["id"], NO_ADAPTATION_REQUIRED),
        ],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])
    result = compute_plan(slice_.to_plan_request())

    assert len(slice_.deviations) == 1
    assert slice_.deviations[0].category_keys == [gluten_key]
    assert slice_.deviations[0].quantity == 3
    assert result.totals.baseline_total == 18
    assert result.totals.deviation_total == 3
    assert result.totals.normal_total == 15


def test_canonical_context_keys_cannot_be_spoofed(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(
        site_id,
        service_date,
        option_ids["alt1"],
        context={"source": "spoofed", "site_id": "spoofed", "keep_me": "yes"},
    )

    assert slice_.context["source"] == "planning_option_review"
    assert slice_.context["site_id"] == site_id
    assert slice_.context["keep_me"] == "yes"


def test_traceability_contains_publication_and_group_identity(app_session) -> None:
    service_date, site_id, dept_a, _dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, include_third_destination=False)
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED)],
    )

    slice_ = _build_slice(site_id, service_date, option_ids["alt1"])

    assert slice_.context["builder_menu_id"]
    assert slice_.context["builder_menu_version"] == 1
    assert slice_.context["builder_menu_row_id"] == option_ids["alt1"]
    assert slice_.context["option_id"] == option_ids["alt1"]
    assert slice_.context["review_id"]
    assert slice_.context["review_basis_hash"]
    assert slice_.context["requirement_group_refs"] == [
        {
            "requirement_group_id": group_a["id"],
            "destination_id": dept_a["id"],
            "unit_id": dept_a["id"],
            "category_keys": slice_.deviations[0].category_keys,
            "quantity": 3,
        }
    ]


def test_deterministic_output_and_acceptance(app_session) -> None:
    service_date, site_id, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=True, dept_b_choice="alt1")
    _save_review(
        site_id,
        service_date,
        option_ids["alt1"],
        [
            _review_payload(dept_a["id"], group_a["id"], ADAPTATION_REQUIRED),
            _review_payload(dept_b["id"], group_b["id"], NO_ADAPTATION_REQUIRED),
        ],
    )

    slice_a = _build_slice(site_id, service_date, option_ids["alt1"], context={"z": 1, "a": 2})
    slice_b = _build_slice(site_id, service_date, option_ids["alt1"], context={"a": 2, "z": 1})

    assert slice_a == slice_b
    assert [unit.unit_id for unit in slice_a.units] == sorted([dept_a["id"], dept_b["id"]])
    assert [deviation.unit_id for deviation in slice_a.deviations] == [dept_a["id"]]

    acceptance = validate_plan_request_for_production(
        slice_a.to_plan_request(),
        expected_unit_ids=[dept_a["id"], dept_b["id"]],
    )
    assert acceptance.accepted is True

    shadow_run = run_plan_request_in_production_shadow(
        slice_a.to_plan_request(),
        expected_unit_ids=[dept_a["id"], dept_b["id"]],
    )
    assert shadow_run.production_acceptance_verdict == "PASS"


def test_cross_tenant_access_fails_closed(app_session) -> None:
    service_date, site_id, _dept_a, _dept_b, _dept_c, _group_a, _group_b, _group_c, option_ids = _build_scenario(app_session, include_groups=False)
    with pytest.raises(KommunOptionReviewPlanningError):
        build_planning_slice_from_option_review(
            tenant_id=2,
            site_id=site_id,
            service_date=service_date,
            meal_key="lunch",
            option_id=option_ids["alt1"],
        )