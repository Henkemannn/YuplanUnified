from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import uuid

import pytest
from flask import current_app
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
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
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.department_menu_choice_repo import MenuChoiceRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)
from core.db import get_new_session, get_session
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.models import DepartmentRequirementGroup, PlanningOptionReview, PlanningOptionReviewDecision
from core.planning_option_review import (
    ADAPTATION_REQUIRED,
    NO_ADAPTATION_REQUIRED,
    PlanningOptionReviewError,
    PlanningOptionReviewService,
    REVIEW_STATE_NO_DEVIATIONS,
    REVIEW_STATE_UNREVIEWED,
    REVIEW_STATE_WITH_DEVIATIONS,
    build_option_review_basis_payload,
    compute_option_review_basis_hash,
)
from core.planera_product2_page2_context import build_product2_page2_planning_context


@dataclass
class ReviewScenario:
    site_id: str
    service_date: date
    year: int
    week: int
    dept_a: dict
    dept_b: dict
    dept_c: dict | None
    group_a: dict | None
    group_b: dict | None
    group_c: dict | None
    option_ids: dict[str, str]


def _build_builder_menu_context_flow() -> tuple[object, CompositionService]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    concrete_builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=InMemoryCompositionAliasRepository(),
        component_alias_repository=InMemoryComponentAliasRepository(),
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=MenuService(composition_repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=InMemoryCompositionAliasRepository(),
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=concrete_builder_flow,
    )
    return menu_context_flow, CompositionService(repository=composition_repository)


def _seed_site(site_id: str, tenant_id: int = 1) -> None:
    db = get_new_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"),
            {"id": site_id, "name": f"Site {site_id}", "tenant_id": tenant_id},
        )
        db.commit()
    finally:
        db.close()


def _seed_department(site_id: str, name: str, resident_count: int = 10) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_requirement(site_id: str, name: str, requirement_key: str) -> int:
    db = get_new_session()
    try:
        db.execute(
            text(
                "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) "
                "VALUES (1, :site_id, :name, 'Övrigt', :requirement_key, 'atomic', 0)"
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


def _seed_group(department_id: str, requirement_ids: list[int], *, quantity: int, label: str) -> dict:
    return DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)


def _build_publication_snapshot(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    day: str,
    builder_menu_id: str,
    builder_menu_version: int,
) -> dict:
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
    composition_service.create_composition(composition_id="comp-alt1", composition_name="Fläskkarré")
    composition_service.create_composition(composition_id="comp-alt2", composition_name="Kokt torsk")
    menu_context_flow.add_composition_menu_row(
        menu_id=builder_menu_id,
        day=day,
        meal_slot="lunch_alt1",
        composition_id="comp-alt1",
        sort_order=10,
    )
    menu_context_flow.add_composition_menu_row(
        menu_id=builder_menu_id,
        day=day,
        meal_slot="lunch_alt2",
        composition_id="comp-alt2",
        sort_order=20,
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


def _seed_scenario(
    app_session,
    *,
    include_groups: bool = True,
    include_unassigned: bool = True,
    dept_b_choice: str = "alt2",
) -> ReviewScenario:
    site_id = f"review-site-{uuid.uuid4()}"
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    with app_session.app_context():
        _seed_site(site_id)
        dept_a = _seed_department(site_id, "Avdelning A", resident_count=18)
        dept_b = _seed_department(site_id, "Avdelning B", resident_count=12)
        dept_c = _seed_department(site_id, "Avdelning C", resident_count=9) if include_unassigned else None

        group_a = group_b = group_c = None
        if include_groups:
            req_a = _seed_requirement(site_id, f"Glutenfri {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
            req_b = _seed_requirement(site_id, f"Vegetarisk {uuid.uuid4().hex[:8]}", f"req_veg_{uuid.uuid4().hex[:8]}")
            group_a = _seed_group(dept_a["id"], [req_a], quantity=3, label="Group A")
            group_b = _seed_group(dept_b["id"], [req_b], quantity=4, label="Group B")
            if dept_c is not None:
                req_c = _seed_requirement(site_id, f"Laktos {uuid.uuid4().hex[:8]}", f"req_lakt_{uuid.uuid4().hex[:8]}")
                group_c = _seed_group(dept_c["id"], [req_c], quantity=2, label="Group C")

        option_ids = _build_publication_snapshot(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            day=service_date.strftime("%A").lower(),
            builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
            builder_menu_version=1,
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
            selected_alt=dept_b_choice,
        )

        return ReviewScenario(
            site_id=site_id,
            service_date=service_date,
            year=year,
            week=week,
            dept_a=dept_a,
            dept_b=dept_b,
            dept_c=dept_c,
            group_a=group_a,
            group_b=group_b,
            group_c=group_c,
            option_ids=option_ids,
        )


def _service() -> PlanningOptionReviewService:
    return PlanningOptionReviewService()


def _decision(destination_id: str, requirement_group_id: str, decision: str) -> dict[str, str]:
    return {
        "destination_id": destination_id,
        "requirement_group_id": requirement_group_id,
        "decision": decision,
    }


def _require_review_row() -> PlanningOptionReview:
    db = get_session()
    try:
        row = db.query(PlanningOptionReview).order_by(PlanningOptionReview.id.desc()).first()
        assert row is not None
        return row
    finally:
        db.close()


def test_unreviewed_state_is_derived_from_absence(app_session) -> None:
    scenario = _seed_scenario(app_session)
    state = _service().get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )

    assert state.review_state == REVIEW_STATE_UNREVIEWED
    assert state.review_is_stale is False
    assert state.relevant_group_count == 1
    assert state.decision_count == 0
    assert state.current_basis_hash is not None


def test_all_no_decisions_reviewed_no_deviations(app_session) -> None:
    scenario = _seed_scenario(app_session)
    state = _service().save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    assert state.review_state == REVIEW_STATE_NO_DEVIATIONS
    assert state.review_is_stale is False
    assert state.relevant_group_count == 1
    assert state.decision_count == 1
    assert state.no_adaptation_count == 1
    assert state.adaptation_count == 0


def test_adaptation_required_marks_review_with_deviations(app_session) -> None:
    scenario = _seed_scenario(app_session)
    state = _service().save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt2"],
        decisions=[_decision(scenario.dept_b["id"], scenario.group_b["id"], ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    assert state.review_state == REVIEW_STATE_WITH_DEVIATIONS
    assert state.review_is_stale is False
    assert state.relevant_group_count == 1
    assert state.decision_count == 1
    assert state.no_adaptation_count == 0
    assert state.adaptation_count == 1


@pytest.mark.parametrize(
    "decisions, error_code",
    [
        ([], "missing_decision"),
        ([{"destination_id": "bogus", "requirement_group_id": "bogus", "decision": NO_ADAPTATION_REQUIRED}], "irrelevant_decision"),
        ([
            _decision("dept-a", "group-a", NO_ADAPTATION_REQUIRED),
            _decision("dept-a", "group-a", ADAPTATION_REQUIRED),
        ], "duplicate_decision"),
    ],
)
def test_invalid_decisions_reject_entire_save(app_session, decisions, error_code) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()

    if error_code == "duplicate_decision":
        decisions = [
            _decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED),
            _decision(scenario.dept_a["id"], scenario.group_a["id"], ADAPTATION_REQUIRED),
        ]

    with pytest.raises(PlanningOptionReviewError, match=error_code):
        service.save_option_review(
            tenant_id=1,
            site_id=scenario.site_id,
            service_date=scenario.service_date,
            meal="lunch",
            option_id=scenario.option_ids["alt1"],
            decisions=decisions,
            reviewed_by_user_id=1,
        )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_state == REVIEW_STATE_UNREVIEWED
    assert state.review_is_stale is False


def test_zero_relevant_groups_can_complete(app_session) -> None:
    scenario = _seed_scenario(app_session, include_groups=False)
    state = _service().save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[],
        reviewed_by_user_id=1,
    )

    assert state.review_state == REVIEW_STATE_NO_DEVIATIONS
    assert state.review_is_stale is False
    assert state.relevant_group_count == 0
    assert state.decision_count == 0


def test_other_option_groups_are_rejected(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()

    with pytest.raises(PlanningOptionReviewError, match="irrelevant_decision"):
        service.save_option_review(
            tenant_id=1,
            site_id=scenario.site_id,
            service_date=scenario.service_date,
            meal="lunch",
            option_id=scenario.option_ids["alt2"],
            decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
            reviewed_by_user_id=1,
        )


def test_unassigned_destination_is_never_included(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()

    with pytest.raises(PlanningOptionReviewError, match="irrelevant_decision"):
        service.save_option_review(
            tenant_id=1,
            site_id=scenario.site_id,
            service_date=scenario.service_date,
            meal="lunch",
            option_id=scenario.option_ids["alt1"],
            decisions=[_decision(scenario.dept_c["id"], scenario.group_c["id"], NO_ADAPTATION_REQUIRED)],
            reviewed_by_user_id=1,
        )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.relevant_group_count == 1


def test_cross_tenant_access_fails_closed(app_session) -> None:
    scenario = _seed_scenario(app_session)
    db = get_session()
    try:
        db.execute(text("INSERT INTO tenants(id, name, active) VALUES (2, 'Tenant 2', 1)"))
        db.commit()
    finally:
        db.close()

    with pytest.raises(PlanningOptionReviewError, match="site_tenant_mismatch"):
        _service().get_option_review_state(
            tenant_id=2,
            site_id=scenario.site_id,
            service_date=scenario.service_date,
            meal="lunch",
            option_id=scenario.option_ids["alt1"],
        )


def test_publication_version_change_makes_previous_review_stale(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    with app_session.app_context():
        _build_publication_snapshot(
            tenant_id=1,
            site_id=scenario.site_id,
            year=scenario.year,
            week=scenario.week,
            day=scenario.service_date.strftime("%A").lower(),
            builder_menu_id=_require_review_row().builder_menu_id,
            builder_menu_version=2,
        )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_destination_reassignment_makes_review_stale(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    MenuChoiceRepo().set_choice(
        tenant_id=1,
        site_id=scenario.site_id,
        department_id=scenario.dept_a["id"],
        year=scenario.year,
        week=scenario.week,
        weekday=scenario.service_date.isocalendar()[2],
        selected_alt="alt2",
    )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_new_relevant_group_makes_review_stale(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    extra_requirement = _seed_requirement(
        scenario.site_id,
        f"Extra {uuid.uuid4().hex[:8]}",
        f"req_extra_{uuid.uuid4().hex[:8]}",
    )
    _seed_group(scenario.dept_a["id"], [extra_requirement], quantity=1, label="Group Extra")

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_removed_or_deactivated_group_makes_review_stale(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    DepartmentRequirementGroupsRepo().update_group(scenario.group_a["id"], is_active=False)

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_effective_quantity_change_does_not_stale_review(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    DepartmentRequirementGroupServiceOverridesRepo().set_override(
        scenario.group_a["id"],
        scenario.service_date,
        "lunch",
        4,
    )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is False
    assert state.review_state == REVIEW_STATE_NO_DEVIATIONS
    assert state.review_basis_hash == state.current_basis_hash
    assert state.relevant_group_count == 1
    assert state.decision_count == 1
    assert state.no_adaptation_count == 1
    assert state.adaptation_count == 0


def test_baseline_quantity_change_does_not_stale_review(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    db = get_session()
    try:
        db.execute(
            text("UPDATE departments SET resident_count_fixed = 25 WHERE id = :department_id"),
            {"department_id": scenario.dept_a["id"]},
        )
        db.commit()
    finally:
        db.close()

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )

    assert state.review_is_stale is False
    assert state.review_state == REVIEW_STATE_NO_DEVIATIONS
    assert state.review_basis_hash == state.current_basis_hash
    assert state.relevant_group_count == 1
    assert state.decision_count == 1


def test_effective_quantity_zero_removes_relevant_group_and_stales_review(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    DepartmentRequirementGroupServiceOverridesRepo().set_override(
        scenario.group_a["id"],
        scenario.service_date,
        "lunch",
        0,
    )

    context = build_product2_page2_planning_context(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
    )
    assert any(group.requirement_group_id == scenario.group_a["id"] for group in context.requirement_groups) is False

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )

    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_requirement_semantics_change_makes_review_stale(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    db = get_session()
    try:
        row = db.execute(
            text("SELECT dietary_type_id FROM department_requirement_group_requirements WHERE group_id = :group_id"),
            {"group_id": scenario.group_a["id"]},
        ).fetchone()
        assert row is not None
        db.execute(
            text("UPDATE dietary_types SET requirement_key = :requirement_key, semantics = 'atomic' WHERE id = :dietary_type_id"),
            {"requirement_key": f"req_changed_{uuid.uuid4().hex[:8]}", "dietary_type_id": int(row[0])},
        )
        db.commit()
    finally:
        db.close()

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_is_stale is True
    assert state.review_state == REVIEW_STATE_UNREVIEWED


def test_rereview_replaces_previous_decision_set(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    first_state = service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )
    second_state = service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    assert first_state.review_id == second_state.review_id
    assert second_state.review_state == REVIEW_STATE_WITH_DEVIATIONS
    assert second_state.adaptation_count == 1
    assert second_state.no_adaptation_count == 0
    assert second_state.decisions == (
        second_state.decisions[0],
    )
    assert second_state.decisions[0].decision == ADAPTATION_REQUIRED


def test_failed_validation_leaves_prior_review_unchanged(app_session) -> None:
    scenario = _seed_scenario(app_session)
    service = _service()
    baseline_state = service.save_option_review(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
        decisions=[_decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED)],
        reviewed_by_user_id=1,
    )

    with pytest.raises(PlanningOptionReviewError, match="irrelevant_decision"):
        service.save_option_review(
            tenant_id=1,
            site_id=scenario.site_id,
            service_date=scenario.service_date,
            meal="lunch",
            option_id=scenario.option_ids["alt1"],
            decisions=[
                _decision(scenario.dept_a["id"], scenario.group_a["id"], NO_ADAPTATION_REQUIRED),
                _decision(scenario.dept_b["id"], scenario.group_b["id"], NO_ADAPTATION_REQUIRED),
            ],
            reviewed_by_user_id=1,
        )

    state = service.get_option_review_state(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        option_id=scenario.option_ids["alt1"],
    )
    assert state.review_id == baseline_state.review_id
    assert state.review_state == REVIEW_STATE_NO_DEVIATIONS
    assert state.decisions == baseline_state.decisions


def test_review_basis_payload_excludes_quantity_and_includes_semantics(app_session) -> None:
    scenario = _seed_scenario(app_session)
    context = build_product2_page2_planning_context(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
    )
    scope_option = next(option for option in context.options if option.option_id == scenario.option_ids["alt1"])
    assigned_destinations = tuple(destination for destination in context.destinations if destination.selected_option_id == scope_option.option_id)
    relevant_groups = tuple(group for group in context.requirement_groups if group.destination_id in {destination.destination_id for destination in assigned_destinations})
    payload = build_option_review_basis_payload(
        tenant_id=1,
        site_id=scenario.site_id,
        service_date=scenario.service_date,
        meal="lunch",
        publication_identity=context.publication_identity,
        option_id=scope_option.option_id,
        assigned_destinations=assigned_destinations,
        relevant_groups=relevant_groups,
    )
    payload_changed_quantity = dict(payload)
    payload_changed_quantity["assigned_destination_ids"] = list(payload["assigned_destination_ids"])
    assert compute_option_review_basis_hash(payload) == compute_option_review_basis_hash(payload_changed_quantity)
    assert payload["relevant_groups"][0]["requirements"][0]["requirement_key"]
