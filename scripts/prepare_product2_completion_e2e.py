from __future__ import annotations

"""Prepare the canonical Product2 completion E2E scenario.

This helper overlays the generic Product2 E2E seed with a deterministic
completion scenario for:

- site: yuplan-e2e-centralkoket
- date: 2026-09-08
- meal: lunch

It is intentionally narrow and idempotent. The base seed remains generic.
"""

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.app_factory import create_app
from core.db import get_session
from core.department_menu_choice_repo import MenuChoiceRepo
from core.models import DepartmentMenuChoice, DepartmentRequirementGroupCompletion, PlanningOptionReview, PlanningOptionReviewDecision
from core.planera_product2_page2_context import build_product2_page2_planning_context
from core.planera_product2_page3_vm import build_product2_page3_vm
from core.planning_option_review import ADAPTATION_REQUIRED, NO_ADAPTATION_REQUIRED, PlanningOptionReviewService
from scripts.seed_product2_e2e import BUILDER_DB_PATH, MAIN_DB_PATH, MEAL, SERVICE_DATE, SITE_ID, TENANT_ID, WEEK, YEAR


TARGET_DEPARTMENT_NAMES = {"Avdelning 11", "Avdelning 13", "Avdelning 16"}
TARGET_MEAL = MEAL
TARGET_SERVICE_DATE = SERVICE_DATE
TARGET_WEEKDAY = TARGET_SERVICE_DATE.isocalendar()[2]


@dataclass(frozen=True)
class CompletionScenarioSummary:
    completion_targets: tuple[tuple[str, str, int], ...]
    review_state: str
    review_decision_count: int
    menu_choice_count: int
    completion_row_count: int
    page3_ready: bool


def _normalize(value: object | None) -> str:
    return str(value or "").strip()


def _build_app(main_db_path: Path, builder_db_path: Path):
    return create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{main_db_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )


def _delete_scenario_reviews(db) -> None:
    review_rows = (
        db.query(PlanningOptionReview)
        .filter_by(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
        )
        .all()
    )
    review_ids = [int(row.id) for row in review_rows]
    if review_ids:
        db.query(PlanningOptionReviewDecision).filter(PlanningOptionReviewDecision.review_id.in_(review_ids)).delete(synchronize_session=False)
    db.query(PlanningOptionReview).filter_by(
        tenant_id=TENANT_ID,
        site_id=SITE_ID,
        service_date=TARGET_SERVICE_DATE,
        meal=TARGET_MEAL,
    ).delete(synchronize_session=False)


def _delete_scenario_completions(db) -> None:
    db.query(DepartmentRequirementGroupCompletion).filter_by(
        service_date=TARGET_SERVICE_DATE,
        meal_key=TARGET_MEAL,
    ).delete(synchronize_session=False)


def _delete_scenario_menu_choices(db, department_ids: list[str]) -> None:
    if not department_ids:
        return
    db.query(DepartmentMenuChoice).filter(
        DepartmentMenuChoice.tenant_id == TENANT_ID,
        DepartmentMenuChoice.site_id == SITE_ID,
        DepartmentMenuChoice.department_id.in_(department_ids),
        DepartmentMenuChoice.year == YEAR,
        DepartmentMenuChoice.week == WEEK,
        DepartmentMenuChoice.weekday == TARGET_WEEKDAY,
        DepartmentMenuChoice.meal == TARGET_MEAL,
    ).delete(synchronize_session=False)


def _delete_weekview_state(db, department_ids: list[str]) -> None:
    if not department_ids:
        return
    if db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='weekview_registrations'")).fetchone() is not None:
        db.execute(
            text(
                "DELETE FROM weekview_registrations "
                "WHERE tenant_id=:tenant_id AND year=:year AND week=:week AND day_of_week=:day_of_week AND meal=:meal AND department_id IN :department_ids"
            ).bindparams(bindparam("department_ids", expanding=True)),
            {
                "tenant_id": str(TENANT_ID),
                "year": YEAR,
                "week": WEEK,
                "day_of_week": TARGET_WEEKDAY,
                "meal": TARGET_MEAL,
                "department_ids": department_ids,
            },
        )
    if db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='weekview_versions'")).fetchone() is not None:
        db.execute(
            text(
                "DELETE FROM weekview_versions "
                "WHERE tenant_id=:tenant_id AND year=:year AND week=:week AND department_id IN :department_ids"
            ).bindparams(bindparam("department_ids", expanding=True)),
            {"tenant_id": str(TENANT_ID), "year": YEAR, "week": WEEK, "department_ids": department_ids},
        )
    if db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='weekview_alt2_flags'")).fetchone() is not None:
        db.execute(
            text(
                "DELETE FROM weekview_alt2_flags "
                "WHERE site_id=:site_id AND year=:year AND week=:week AND day_of_week=:day_of_week AND department_id IN :department_ids"
            ).bindparams(bindparam("department_ids", expanding=True)),
            {
                "site_id": SITE_ID,
                "year": YEAR,
                "week": WEEK,
                "day_of_week": TARGET_WEEKDAY,
                "department_ids": department_ids,
            },
        )


def _semantic_requirement_names(group) -> frozenset[str]:
    return frozenset(_normalize(requirement.name) for requirement in group.requirements if _normalize(requirement.name))


def _build_canonical_decisions(context) -> list[dict[str, str]]:
    dept_name_by_id = {str(destination.destination_id): str(destination.display_name) for destination in context.destinations}
    wanted = {
        ("Avdelning 11", frozenset({"Glutenfri"})): ADAPTATION_REQUIRED,
        ("Avdelning 11", frozenset({"Laktosfri"})): NO_ADAPTATION_REQUIRED,
        ("Avdelning 11", frozenset({"Äggfri"})): NO_ADAPTATION_REQUIRED,
        ("Avdelning 13", frozenset({"Timbal", "Laktosfri"})): ADAPTATION_REQUIRED,
        ("Avdelning 16", frozenset({"Glutenfri"})): ADAPTATION_REQUIRED,
        ("Avdelning 16", frozenset({"Vegetarisk", "Äggfri"})): ADAPTATION_REQUIRED,
    }
    decisions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in context.requirement_groups:
        department_name = dept_name_by_id.get(str(group.destination_id), "")
        semantic_names = _semantic_requirement_names(group)
        decision = wanted.get((department_name, semantic_names))
        if decision is None:
            continue
        key = (str(group.destination_id), str(group.requirement_group_id))
        if key in seen:
            raise RuntimeError(f"duplicate target group mapping:{department_name}:{group.requirement_group_id}")
        seen.add(key)
        decisions.append(
            {
                "destination_id": str(group.destination_id),
                "requirement_group_id": str(group.requirement_group_id),
                "decision": decision,
            }
        )
    if len(decisions) != 6:
        raise RuntimeError(f"canonical_decisions_incomplete:{len(decisions)}")
    return decisions


def _build_alt2_no_deviation_decisions(context) -> list[dict[str, str]]:
    dept_name_by_id = {str(destination.destination_id): str(destination.display_name) for destination in context.destinations}
    decisions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in context.requirement_groups:
        department_name = dept_name_by_id.get(str(group.destination_id), "")
        if department_name in TARGET_DEPARTMENT_NAMES:
            continue
        key = (str(group.destination_id), str(group.requirement_group_id))
        if key in seen:
            raise RuntimeError(f"duplicate alt2 target group mapping:{department_name}:{group.requirement_group_id}")
        seen.add(key)
        decisions.append(
            {
                "destination_id": str(group.destination_id),
                "requirement_group_id": str(group.requirement_group_id),
                "decision": NO_ADAPTATION_REQUIRED,
            }
        )
    if len(decisions) != 11:
        raise RuntimeError(f"alt2_decisions_incomplete:{len(decisions)}")
    return decisions


def _set_scenario_menu_choices(context) -> None:
    dept_by_name = {str(destination.display_name): str(destination.destination_id) for destination in context.destinations}
    grouped_departments = sorted({str(group.destination_id) for group in context.requirement_groups})
    repo = MenuChoiceRepo()
    for department_name, department_id in dept_by_name.items():
        department_number = int(department_name.split()[-1])
        if department_id in grouped_departments:
            selected_alt = "alt1" if department_name in TARGET_DEPARTMENT_NAMES else "alt2"
        else:
            selected_alt = "alt1" if department_number <= 10 else "alt2"
        repo.set_choice(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            department_id=department_id,
            year=YEAR,
            week=WEEK,
            weekday=TARGET_WEEKDAY,
            selected_alt=selected_alt,
        )


def prepare_product2_completion_e2e(
    *,
    main_db_path: Path = MAIN_DB_PATH,
    builder_db_path: Path = BUILDER_DB_PATH,
) -> CompletionScenarioSummary:
    app = _build_app(main_db_path, builder_db_path)
    with app.app_context():
        initial_context = build_product2_page2_planning_context(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
        )
        department_ids = [str(destination.destination_id) for destination in initial_context.destinations]

        db = get_session()
        try:
            _delete_scenario_reviews(db)
            _delete_scenario_completions(db)
            _delete_scenario_menu_choices(db, department_ids)
            _delete_weekview_state(db, department_ids)
            db.commit()
        finally:
            db.close()

        _set_scenario_menu_choices(initial_context)

        context = build_product2_page2_planning_context(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
        )
        decisions = _build_canonical_decisions(context)
        alt1_option = next((option for option in context.options if str(option.variant_type) == "alt1"), None)
        if alt1_option is None:
            raise RuntimeError("missing_alt1_option")
        alt2_option = next((option for option in context.options if str(option.variant_type) == "alt2"), None)
        if alt2_option is None:
            raise RuntimeError("missing_alt2_option")

        review_state = PlanningOptionReviewService().save_option_review(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
            option_id=str(alt1_option.option_id),
            decisions=decisions,
            reviewed_by_user_id=1,
        )

        alt2_decisions = _build_alt2_no_deviation_decisions(context)
        PlanningOptionReviewService().save_option_review(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
            option_id=str(alt2_option.option_id),
            decisions=alt2_decisions,
            reviewed_by_user_id=1,
        )

        vm = build_product2_page3_vm(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            service_date=TARGET_SERVICE_DATE,
            meal=TARGET_MEAL,
        )

        db = get_session()
        try:
            completion_row_count = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM department_requirement_group_completions "
                        "WHERE service_date=:service_date AND meal_key=:meal_key"
                    ),
                    {"service_date": TARGET_SERVICE_DATE, "meal_key": TARGET_MEAL},
                ).scalar()
                or 0
            )
            menu_choice_count = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM department_menu_choices "
                        "WHERE site_id=:site_id AND year=:year AND week=:week AND meal=:meal AND weekday=:weekday"
                    ),
                    {"site_id": SITE_ID, "year": YEAR, "week": WEEK, "meal": TARGET_MEAL, "weekday": TARGET_WEEKDAY},
                ).scalar()
                or 0
            )
        finally:
            db.close()

        return CompletionScenarioSummary(
            completion_targets=tuple(
                (str(target.destination_id), str(target.requirement_group_id), int(target.quantity))
                for target in vm.completion_targets
            ),
            review_state=str(review_state.review_state),
            review_decision_count=int(review_state.decision_count),
            menu_choice_count=menu_choice_count,
            completion_row_count=completion_row_count,
            page3_ready=bool(vm.ready),
        )


def _main() -> int:
    if os.getenv("APP_ENV", "local").lower() not in {"local", "development", "dev", "test"}:
        raise SystemExit("Refusing to prepare completion fixture outside local/test environments.")
    summary = prepare_product2_completion_e2e()
    print(
        {
            "site_id": SITE_ID,
            "service_date": TARGET_SERVICE_DATE.isoformat(),
            "meal": TARGET_MEAL,
            "review_state": summary.review_state,
            "review_decision_count": summary.review_decision_count,
            "menu_choice_count": summary.menu_choice_count,
            "completion_row_count": summary.completion_row_count,
            "page3_ready": summary.page3_ready,
            "completion_targets": summary.completion_targets,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())