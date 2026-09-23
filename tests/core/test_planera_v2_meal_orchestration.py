from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from typing import get_args

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo
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
from core.db import get_new_session, get_session
from core.department_menu_choice_repo import MenuChoiceRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planera_product2_page2_context import build_product2_page2_planning_context
from core.planera_v2.acceptance import ProductionAcceptanceResult, validate_plan_request_for_production
from core.planera_v2.domain import Deviation, PlanRequest, PlanningSlice, UnitInput
from core.planera_v2.engine import compute_plan
from core.planera_v2.meal_orchestration import (
    KommunMealDestinationResult,
    KommunMealOptionResult,
    KommunMealOrchestrationError,
    KommunMealOrchestrationResult,
    MealBlockerCode,
    run_kommun_meal_orchestration,
)
from core.planning_option_review import (
    ADAPTATION_REQUIRED,
    NO_ADAPTATION_REQUIRED,
    REVIEW_STATE_NO_DEVIATIONS,
    REVIEW_STATE_UNREVIEWED,
    REVIEW_STATE_WITH_DEVIATIONS,
    PlanningOptionReviewService,
)
from scripts.seed_product2_e2e import BUILDER_DB_PATH, MAIN_DB_PATH, SERVICE_DATE, SITE_ID, WEEK, YEAR


def _python_executable() -> str:
    return sys.executable


def _seed_script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "seed_product2_e2e.py"


def _seed_via_subprocess() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "local",
            "FLASK_ENV": "local",
            "DEPLOY_ENV": "local",
            "DATABASE_URL": f"sqlite:///{MAIN_DB_PATH.as_posix()}",
            "BUILDER_DB_PATH": str(BUILDER_DB_PATH),
        }
    )
    return subprocess.run(
        [_python_executable(), str(_seed_script_path())],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _cleanup_seed_db_state() -> None:
    import core.db as core_db

    session_factory = getattr(core_db, "_SessionFactory", None)
    if session_factory is not None:
        try:
            session_factory.remove()
        except Exception:
            pass
    engine = getattr(core_db, "_engine", None)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass


def _build_builder_menu_context_flow() -> tuple[BuilderMenuContextFlow, CompositionService]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    builder_flow = BuilderFlow(
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
        library_flow=builder_flow,
    )
    return menu_context_flow, CompositionService(repository=composition_repository)


def _seed_minimal_publication(
    *,
    app,
    site_id: str,
    year: int,
    week: int,
    day: str,
    builder_menu_id: str,
    variant_types: tuple[str, ...] = ("alt1",),
) -> dict[str, str]:
    with app.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        previous_builder_menu_context_flow = app.extensions.get("builder_menu_context_flow")
        previous_builder_flow = app.extensions.get("builder_flow")
        app.extensions["builder_menu_context_flow"] = builder_flow
        app.extensions["builder_flow"] = builder_flow
        try:
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
                composition_id, composition_name = composition_names.get(variant_type, (f"comp-{variant_type}", variant_type))
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
                projection_snapshot_json=json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            )
            return {
                str(row.variant_type): str(row.builder_menu_row_id)
                for row in outcome.projection.rows
                if str(row.day) == day and str(row.meal) == "lunch"
            }
        finally:
            if previous_builder_menu_context_flow is None:
                app.extensions.pop("builder_menu_context_flow", None)
            else:
                app.extensions["builder_menu_context_flow"] = previous_builder_menu_context_flow
            if previous_builder_flow is None:
                app.extensions.pop("builder_flow", None)
            else:
                app.extensions["builder_flow"] = previous_builder_flow


@dataclass(frozen=True)
class _StubReviewState:
    review_state: str
    review_is_stale: bool = False


@dataclass(frozen=True)
class _SyntheticOption:
    option_id: str
    display_title: str


@dataclass(frozen=True)
class _SyntheticDestination:
    destination_id: str
    display_name: str
    baseline_quantity: int
    selected_option_id: str | None
    choice_source: str


@dataclass(frozen=True)
class _SyntheticContext:
    status: str
    publication_identity: object | None
    options: tuple[_SyntheticOption, ...]
    destinations: tuple[_SyntheticDestination, ...]


def _synthetic_context(
    *,
    options: tuple[_SyntheticOption, ...],
    destinations: tuple[_SyntheticDestination, ...],
    status: str = "ok",
) -> _SyntheticContext:
    return _SyntheticContext(
        status=status,
        publication_identity=object() if status == "ok" else None,
        options=options,
        destinations=destinations,
    )


def _decisions_for_option(context: _SyntheticContext, option_id: str, decision: str) -> list[dict[str, str]]:
    relevant_destination_ids = {destination.destination_id for destination in context.destinations if destination.selected_option_id == option_id}
    return [
        {
            "destination_id": group.destination_id,
            "requirement_group_id": group.requirement_group_id,
            "decision": decision,
        }
        for group in context.requirement_groups
        if group.destination_id in relevant_destination_ids
    ]


def _review_decisions_for_option(context, option_id: str, decision: str) -> list[dict[str, str]]:
    relevant_destination_ids = {destination.destination_id for destination in context.destinations if destination.selected_option_id == option_id}
    return [
        {
            "destination_id": group.destination_id,
            "requirement_group_id": group.requirement_group_id,
            "decision": decision,
        }
        for group in context.requirement_groups
        if group.destination_id in relevant_destination_ids
    ]


def _make_real_review_context(app, *, site_id: str):
    with app.app_context():
        db = get_new_session()
        try:
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, 1, 0)"),
                {"id": site_id, "name": site_id},
            )
            db.commit()
        finally:
            db.close()

        department, _ = DepartmentsRepo().create_department(
            site_id=site_id,
            name="Avdelning A",
            resident_count_mode="fixed",
            resident_count_fixed=18,
        )

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) "
                    "VALUES (1, :site_id, :name, 'Övrigt', :requirement_key, 'atomic', 0)"
                ),
                {"site_id": site_id, "name": "Glutenfri", "requirement_key": f"req_{site_id}"},
            )
            db.commit()
            row = db.execute(
                text("SELECT id FROM dietary_types WHERE site_id=:site_id AND requirement_key=:requirement_key"),
                {"site_id": site_id, "requirement_key": f"req_{site_id}"},
            ).fetchone()
            assert row is not None
            requirement_id = int(row[0])
        finally:
            db.close()

        group = DepartmentRequirementGroupsRepo().create_group(
            department["id"],
            3,
            [requirement_id],
            label="Group A",
        )
        option_ids = _seed_minimal_publication(
            app=app,
            site_id=site_id,
            year=YEAR,
            week=WEEK,
            day=SERVICE_DATE.strftime("%A").lower(),
            builder_menu_id=f"builder-{site_id}",
        )
        MenuChoiceRepo().set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=department["id"],
            year=YEAR,
            week=WEEK,
            weekday=SERVICE_DATE.isocalendar()[2],
            selected_alt="alt1",
        )
        return department, group, option_ids


def _load_counts() -> dict[str, int]:
    db = get_session()
    try:
        return {
            "departments": int(db.execute(text("SELECT COUNT(*) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "dietary_types": int(db.execute(text("SELECT COUNT(*) FROM dietary_types WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "groups": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_groups g JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "zero_group_departments": int(db.execute(text("SELECT COUNT(*) FROM (SELECT d.id FROM departments d LEFT JOIN department_requirement_groups g ON g.department_id = d.id WHERE d.site_id=:site_id GROUP BY d.id HAVING COUNT(g.id)=0) x"), {"site_id": SITE_ID}).scalar() or 0),
            "multi_group_departments": int(db.execute(text("SELECT COUNT(*) FROM (SELECT d.id FROM departments d JOIN department_requirement_groups g ON g.department_id = d.id WHERE d.site_id=:site_id GROUP BY d.id HAVING COUNT(g.id) > 1) x"), {"site_id": SITE_ID}).scalar() or 0),
            "multi_requirement_groups": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_groups g JOIN (SELECT group_id, COUNT(*) c FROM department_requirement_group_requirements GROUP BY group_id HAVING COUNT(*) > 1) x ON x.group_id = g.id JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "choices": int(db.execute(text("SELECT COUNT(*) FROM department_menu_choices WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "publications": int(db.execute(text("SELECT COUNT(*) FROM commun_builder_publication_pins WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "overrides": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_group_service_overrides o JOIN department_requirement_groups g ON g.id = o.group_id JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_total": int(db.execute(text("SELECT COALESCE(SUM(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_min": int(db.execute(text("SELECT COALESCE(MIN(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_max": int(db.execute(text("SELECT COALESCE(MAX(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "kitchen_users": int(db.execute(text("SELECT COUNT(*) FROM users WHERE lower(email)=:email AND role='kitchen'"), {"email": 'e2e.kitchen@yuplan.local'}).scalar() or 0),
            "kitchen_bindings": int(db.execute(text("SELECT COUNT(*) FROM kitchen_user_sites k JOIN users u ON u.id = k.user_id WHERE lower(u.email)=:email AND k.site_id=:site_id"), {"email": 'e2e.kitchen@yuplan.local', "site_id": SITE_ID}).scalar() or 0),
        }
    finally:
        db.close()


def test_public_api_and_result_model_contract() -> None:
    assert [field.name for field in fields(KommunMealOrchestrationResult)] == [
        "tenant_id",
        "site_id",
        "service_date",
        "meal",
        "publication_identity",
        "options",
        "unassigned_destinations",
        "blockers",
        "ready",
    ]
    assert [field.name for field in fields(KommunMealOptionResult)] == [
        "option_id",
        "display_title",
        "assigned_destination_ids",
        "assigned_destination_count",
        "has_demand",
        "requires_review",
        "review_state",
        "review_is_stale",
        "blockers",
        "planning_slice",
        "plan_result",
        "acceptance_issues",
    ]
    assert [field.name for field in fields(KommunMealDestinationResult)] == [
        "destination_id",
        "display_name",
        "baseline_quantity",
        "selected_option_id",
        "choice_source",
    ]
    assert set(get_args(MealBlockerCode)) == {
        "UNASSIGNED_DESTINATIONS",
        "UNREVIEWED_OPTIONS",
        "STALE_REVIEWS",
        "INVALID_OPTION_PLAN",
    }


def test_rejects_unsupported_meal() -> None:
    with pytest.raises(KommunMealOrchestrationError, match="meal_unsupported"):
        run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1), meal="breakfast")


def test_zero_demand_option_is_bypassed_and_does_not_block_ready_meal(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _synthetic_context(
        options=(
            _SyntheticOption(option_id="opt-zero", display_title="Zero demand"),
            _SyntheticOption(option_id="opt-live", display_title="Live demand"),
        ),
        destinations=(
            _SyntheticDestination(
                destination_id="dest-live",
                display_name="Destination Live",
                baseline_quantity=18,
                selected_option_id="opt-live",
                choice_source="explicit",
            ),
        ),
    )
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", lambda **_: context)

    calls: list[str] = []

    class _ReviewService:
        def get_option_review_state(self, **kwargs: object) -> _StubReviewState:
            calls.append(f"review:{kwargs['option_id']}")
            return _StubReviewState(review_state=REVIEW_STATE_NO_DEVIATIONS)

    def _slice_builder(**kwargs: object) -> PlanningSlice:
        calls.append(f"slice:{kwargs['option_id']}")
        return PlanningSlice(
            baseline=18,
            units=(UnitInput(unit_id="dest-live", baseline_total=18),),
            deviations=(),
            context={"kind": "ready"},
        )

    monkeypatch.setattr("core.planera_v2.meal_orchestration.PlanningOptionReviewService", lambda: _ReviewService())
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_planning_slice_from_option_review", _slice_builder)

    result = run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))

    zero_option = next(option for option in result.options if option.option_id == "opt-zero")
    live_option = next(option for option in result.options if option.option_id == "opt-live")

    assert calls == ["review:opt-live", "slice:opt-live"]
    assert result.ready is True
    assert result.blockers == ()
    assert zero_option.has_demand is False
    assert zero_option.requires_review is False
    assert zero_option.planning_slice is None
    assert zero_option.plan_result is None
    assert live_option.plan_result is not None
    assert live_option.planning_slice is not None


def test_unreviewed_option_blocks_without_adapter_or_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _synthetic_context(
        options=(_SyntheticOption(option_id="opt-1", display_title="Option 1"),),
        destinations=(
            _SyntheticDestination(
                destination_id="dest-1",
                display_name="Destination 1",
                baseline_quantity=18,
                selected_option_id="opt-1",
                choice_source="explicit",
            ),
        ),
    )
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", lambda **_: context)

    class _ReviewService:
        def get_option_review_state(self, **_: object) -> _StubReviewState:
            return _StubReviewState(review_state=REVIEW_STATE_UNREVIEWED)

    def _boom(*_: object, **__: object) -> object:
        raise AssertionError("adapter or engine should not run for unreviewed options")

    monkeypatch.setattr("core.planera_v2.meal_orchestration.PlanningOptionReviewService", lambda: _ReviewService())
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_planning_slice_from_option_review", _boom)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.compute_plan", _boom)

    result = run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))

    option = result.options[0]
    assert result.ready is False
    assert result.blockers == ("UNREVIEWED_OPTIONS",)
    assert option.blockers == ("UNREVIEWED_OPTIONS",)
    assert option.planning_slice is None
    assert option.plan_result is None


def test_stale_review_blocks_without_adapter_or_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _synthetic_context(
        options=(_SyntheticOption(option_id="opt-1", display_title="Option 1"),),
        destinations=(
            _SyntheticDestination(
                destination_id="dest-1",
                display_name="Destination 1",
                baseline_quantity=18,
                selected_option_id="opt-1",
                choice_source="explicit",
            ),
        ),
    )
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", lambda **_: context)

    class _ReviewService:
        def get_option_review_state(self, **_: object) -> _StubReviewState:
            return _StubReviewState(review_state=REVIEW_STATE_UNREVIEWED, review_is_stale=True)

    def _boom(*_: object, **__: object) -> object:
        raise AssertionError("adapter or engine should not run for stale reviews")

    monkeypatch.setattr("core.planera_v2.meal_orchestration.PlanningOptionReviewService", lambda: _ReviewService())
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_planning_slice_from_option_review", _boom)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.compute_plan", _boom)

    result = run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))

    option = result.options[0]
    assert result.ready is False
    assert result.blockers == ("STALE_REVIEWS",)
    assert option.blockers == ("STALE_REVIEWS",)
    assert option.review_is_stale is True
    assert option.planning_slice is None
    assert option.plan_result is None


def test_structural_adapter_error_maps_to_invalid_option_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _synthetic_context(
        options=(_SyntheticOption(option_id="opt-1", display_title="Option 1"),),
        destinations=(
            _SyntheticDestination(
                destination_id="dest-1",
                display_name="Destination 1",
                baseline_quantity=18,
                selected_option_id="opt-1",
                choice_source="explicit",
            ),
        ),
    )
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", lambda **_: context)

    class _ReviewService:
        def get_option_review_state(self, **_: object) -> _StubReviewState:
            return _StubReviewState(review_state=REVIEW_STATE_NO_DEVIATIONS)

    def _raise_adapter(*_: object, **__: object) -> PlanningSlice:
        from core.planera_v2.adapters.kommun_from_option_reviews import KommunOptionReviewPlanningError

        raise KommunOptionReviewPlanningError("missing_decision", "missing decision")

    def _boom(*_: object, **__: object) -> object:
        raise AssertionError("engine should not run when adapter fails")

    monkeypatch.setattr("core.planera_v2.meal_orchestration.PlanningOptionReviewService", lambda: _ReviewService())
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_planning_slice_from_option_review", _raise_adapter)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.validate_plan_request_for_production", _boom)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.compute_plan", _boom)

    result = run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))

    option = result.options[0]
    assert result.ready is False
    assert result.blockers == ("INVALID_OPTION_PLAN",)
    assert option.blockers == ("INVALID_OPTION_PLAN",)
    assert option.planning_slice is None
    assert option.plan_result is None


def test_acceptance_rejection_maps_to_invalid_option_plan_and_skips_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _synthetic_context(
        options=(_SyntheticOption(option_id="opt-1", display_title="Option 1"),),
        destinations=(
            _SyntheticDestination(
                destination_id="dest-1",
                display_name="Destination 1",
                baseline_quantity=18,
                selected_option_id="opt-1",
                choice_source="explicit",
            ),
        ),
    )
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", lambda **_: context)

    class _ReviewService:
        def get_option_review_state(self, **_: object) -> _StubReviewState:
            return _StubReviewState(review_state=REVIEW_STATE_NO_DEVIATIONS)

    def _slice_builder(**_: object) -> PlanningSlice:
        return PlanningSlice(
            baseline=18,
            units=(UnitInput(unit_id="dest-1", baseline_total=18),),
            deviations=(Deviation(form="timbal", category_keys=["ej_fisk"], quantity=3, unit_id="dest-1"),),
            context={"kind": "acceptance_rejection"},
        )

    def _reject(request: PlanRequest, *, expected_unit_ids=None) -> ProductionAcceptanceResult:
        assert expected_unit_ids == ("dest-1",)
        return ProductionAcceptanceResult(
            accepted=False,
            issues=(
                __import__("core.planera_v2.acceptance", fromlist=["ProductionAcceptanceIssue"]).ProductionAcceptanceIssue(
                    code="unexpected_unit",
                    severity="error",
                    message="unexpected unit",
                    unit_id="dest-1",
                ),
            ),
        )

    def _boom(*_: object, **__: object) -> object:
        raise AssertionError("engine must not run when acceptance rejects")

    monkeypatch.setattr("core.planera_v2.meal_orchestration.PlanningOptionReviewService", lambda: _ReviewService())
    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_planning_slice_from_option_review", _slice_builder)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.validate_plan_request_for_production", _reject)
    monkeypatch.setattr("core.planera_v2.meal_orchestration.compute_plan", _boom)

    result = run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))

    option = result.options[0]
    assert result.ready is False
    assert result.blockers == ("INVALID_OPTION_PLAN",)
    assert option.blockers == ("INVALID_OPTION_PLAN",)
    assert option.acceptance_issues[0].code == "unexpected_unit"
    assert option.plan_result is None


def test_unexpected_exception_fails_hard(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(**_: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr("core.planera_v2.meal_orchestration.build_product2_page2_planning_context", _explode)

    with pytest.raises(KommunMealOrchestrationError, match="context_error"):
        run_kommun_meal_orchestration(tenant_id=1, site_id="site", service_date=date(2026, 1, 1))


def test_exact_engine_result_reaches_real_engine(app_session) -> None:
    site_id = f"meal-engine-{uuid.uuid4().hex[:8]}"
    department, group, option_ids = _make_real_review_context(app_session, site_id=site_id)

    service = PlanningOptionReviewService()
    save_state = service.save_option_review(
        tenant_id=1,
        site_id=site_id,
        service_date=SERVICE_DATE,
        meal="lunch",
        option_id=option_ids["alt1"],
        decisions=[
            {
                "destination_id": department["id"],
                "requirement_group_id": group["id"],
                "decision": ADAPTATION_REQUIRED,
            }
        ],
        reviewed_by_user_id=1,
    )
    assert save_state.review_state == REVIEW_STATE_WITH_DEVIATIONS

    result = run_kommun_meal_orchestration(
        tenant_id=1,
        site_id=site_id,
        service_date=SERVICE_DATE,
        meal="lunch",
    )

    option = next(item for item in result.options if item.option_id == option_ids["alt1"])
    assert result.ready is True
    assert result.blockers == ()
    assert option.plan_result is not None
    assert option.plan_result.totals.baseline_total == 18
    assert option.plan_result.totals.deviation_total == 3
    assert option.plan_result.totals.normal_total == 15


def test_real_e2e_initial_state_blocks_unreviewed_and_unassigned(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    result = _seed_via_subprocess()
    assert result.returncode == 0, result.stderr or result.stdout

    temp_main_db = tmp_path / "product2_e2e.db"
    temp_builder_db = tmp_path / "product2_e2e_builder.db"
    shutil.copy2(MAIN_DB_PATH, temp_main_db)
    shutil.copy2(BUILDER_DB_PATH, temp_builder_db)

    try:
        from core.app_factory import create_app

        app = create_app(
            {
                "TESTING": True,
                "database_url": f"sqlite:///{temp_main_db.as_posix()}",
                "BUILDER_DB_PATH": str(temp_builder_db),
            }
        )
        with app.app_context():
            context = build_product2_page2_planning_context(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            meal_result = run_kommun_meal_orchestration(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )

            assert context.status == "ok"
            assert context.publication_identity is not None
            assert len(context.destinations) == 18
            assert len(context.options) == 2
            assert len(context.requirement_groups) == 17
            assert sum(1 for destination in context.destinations if destination.selected_option_id == context.options[0].option_id) == 10
            assert sum(1 for destination in context.destinations if destination.selected_option_id == context.options[1].option_id) == 7
            assert sum(1 for destination in context.destinations if destination.selected_option_id is None) == 1

            assert meal_result.ready is False
            assert meal_result.blockers == ("UNASSIGNED_DESTINATIONS", "UNREVIEWED_OPTIONS")
            assert len(meal_result.options) == 2
            assert len(meal_result.unassigned_destinations) == 1
            assert all(option.has_demand is True for option in meal_result.options)
            assert all(option.plan_result is None for option in meal_result.options)
            assert all(option.review_state == REVIEW_STATE_UNREVIEWED for option in meal_result.options)
            assert all(option.review_is_stale is False for option in meal_result.options)
            unassigned_id = meal_result.unassigned_destinations[0].destination_id
            assert all(unassigned_id not in option.assigned_destination_ids for option in meal_result.options)
    finally:
        _cleanup_seed_db_state()


def test_ready_stale_re_review_transition(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    result = _seed_via_subprocess()
    assert result.returncode == 0, result.stderr or result.stdout

    temp_main_db = tmp_path / "product2_e2e.db"
    temp_builder_db = tmp_path / "product2_e2e_builder.db"
    shutil.copy2(MAIN_DB_PATH, temp_main_db)
    shutil.copy2(BUILDER_DB_PATH, temp_builder_db)

    try:
        from core.app_factory import create_app

        app = create_app(
            {
                "TESTING": True,
                "database_url": f"sqlite:///{temp_main_db.as_posix()}",
                "BUILDER_DB_PATH": str(temp_builder_db),
            }
        )
        with app.app_context():
            service = PlanningOptionReviewService()
            context = build_product2_page2_planning_context(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            option1 = next(option for option in context.options if option.variant_type == "alt1")
            option2 = next(option for option in context.options if option.variant_type == "alt2")

            def _save_review(option_id: str, decision: str = NO_ADAPTATION_REQUIRED) -> None:
                current_context = build_product2_page2_planning_context(
                    tenant_id=1,
                    site_id=SITE_ID,
                    service_date=SERVICE_DATE,
                    meal="lunch",
                )
                assigned_destination_ids = {
                    destination.destination_id
                    for destination in current_context.destinations
                    if destination.selected_option_id == option_id
                }
                decisions = [
                    {
                        "destination_id": group.destination_id,
                        "requirement_group_id": group.requirement_group_id,
                        "decision": decision,
                    }
                    for group in current_context.requirement_groups
                    if group.destination_id in assigned_destination_ids
                ]
                save_state = service.save_option_review(
                    tenant_id=1,
                    site_id=SITE_ID,
                    service_date=SERVICE_DATE,
                    meal="lunch",
                    option_id=option_id,
                    decisions=decisions,
                    reviewed_by_user_id=1,
                )
                assert save_state.review_state in {REVIEW_STATE_NO_DEVIATIONS, REVIEW_STATE_WITH_DEVIATIONS}

            _save_review(option1.option_id)
            _save_review(option2.option_id)

            first_result = run_kommun_meal_orchestration(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            assert first_result.ready is False
            assert first_result.blockers == ("UNASSIGNED_DESTINATIONS",)
            assert len(first_result.unassigned_destinations) == 1
            assert all(option.plan_result is not None for option in first_result.options)

            unassigned_destination = next(destination for destination in context.destinations if destination.selected_option_id is None)
            MenuChoiceRepo().set_choice(
                tenant_id=1,
                site_id=SITE_ID,
                department_id=unassigned_destination.destination_id,
                year=YEAR,
                week=WEEK,
                weekday=SERVICE_DATE.isocalendar()[2],
                selected_alt=option1.variant_type,
            )

            stale_state = service.get_option_review_state(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
                option_id=option1.option_id,
            )
            assert stale_state.review_is_stale is True
            assert stale_state.review_state == REVIEW_STATE_UNREVIEWED

            stale_result = run_kommun_meal_orchestration(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            assert stale_result.ready is False
            assert stale_result.blockers == ("STALE_REVIEWS",)
            assert any(option.option_id == option1.option_id and option.plan_result is None for option in stale_result.options)

            _save_review(option1.option_id)

            ready_result = run_kommun_meal_orchestration(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            assert ready_result.ready is True
            assert ready_result.blockers == ()
            assert len(ready_result.unassigned_destinations) == 0
            assert all(option.plan_result is not None for option in ready_result.options)
    finally:
        _cleanup_seed_db_state()
