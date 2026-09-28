from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session
from core.planera_product2_page2_context import build_product2_page2_planning_context
from core.planera_product2_page3_vm import build_product2_page3_vm
from core.planning_option_review import ADAPTATION_REQUIRED, NO_ADAPTATION_REQUIRED, PlanningOptionReviewService
from scripts import seed_product2_e2e as base_seed
from scripts.prepare_product2_completion_e2e import prepare_product2_completion_e2e


def _restore_environment(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _seed_temp_base_dataset(monkeypatch, main_db_path: Path, builder_db_path: Path):
    monkeypatch.setattr(base_seed, "MAIN_DB_PATH", main_db_path)
    monkeypatch.setattr(base_seed, "BUILDER_DB_PATH", builder_db_path)
    env_snapshot = {
        key: os.environ.get(key)
        for key in ("APP_ENV", "FLASK_ENV", "DEPLOY_ENV", "DATABASE_URL", "BUILDER_DB_PATH")
    }
    try:
        result = base_seed._seed()
        assert Path(result.main_db_path) == main_db_path
        assert Path(result.builder_db_path) == builder_db_path
    finally:
        _restore_environment(env_snapshot)


def _group_lookup(context):
    dept_name_by_id = {str(destination.destination_id): str(destination.display_name) for destination in context.destinations}
    lookup: dict[tuple[str, frozenset[str]], str] = {}
    for group in context.requirement_groups:
        req_names = frozenset(str(requirement.name).strip() for requirement in group.requirements if str(requirement.name).strip())
        lookup[(dept_name_by_id[str(group.destination_id)], req_names)] = str(group.requirement_group_id)
    return lookup


def test_prepare_product2_completion_e2e_builds_canonical_four_target_scenario(tmp_path, monkeypatch):
    main_db_path = tmp_path / "product2_e2e.db"
    builder_db_path = tmp_path / "product2_e2e_builder.db"

    _seed_temp_base_dataset(monkeypatch, main_db_path, builder_db_path)

    summary = prepare_product2_completion_e2e(main_db_path=main_db_path, builder_db_path=builder_db_path)
    assert len(summary.completion_targets) == 4
    assert summary.review_state == "REVIEWED_WITH_DEVIATIONS"
    assert summary.review_decision_count == 6
    assert summary.completion_row_count == 0
    assert summary.page3_ready is True

    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{main_db_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )

    with app.app_context():
        context = build_product2_page2_planning_context(
            tenant_id=1,
            site_id=base_seed.SITE_ID,
            service_date=base_seed.SERVICE_DATE,
            meal=base_seed.MEAL,
        )
        options_by_variant = {str(option.variant_type): option for option in context.options}
        alt1_option = options_by_variant["alt1"]

        destinations = {destination.display_name: destination for destination in context.destinations}
        assert destinations["Avdelning 11"].selected_option_id == alt1_option.option_id
        assert destinations["Avdelning 13"].selected_option_id == alt1_option.option_id
        assert destinations["Avdelning 16"].selected_option_id == alt1_option.option_id

        review_state = PlanningOptionReviewService().get_option_review_state(
            tenant_id=1,
            site_id=base_seed.SITE_ID,
            service_date=base_seed.SERVICE_DATE,
            meal=base_seed.MEAL,
            option_id=alt1_option.option_id,
        )
        assert review_state.review_state == "REVIEWED_WITH_DEVIATIONS"
        assert review_state.decision_count == 6
        assert review_state.adaptation_count == 4
        assert review_state.no_adaptation_count == 2

        alt2_state = PlanningOptionReviewService().get_option_review_state(
            tenant_id=1,
            site_id=base_seed.SITE_ID,
            service_date=base_seed.SERVICE_DATE,
            meal=base_seed.MEAL,
            option_id=options_by_variant["alt2"].option_id,
        )
        assert alt2_state.review_state == "REVIEWED_NO_DEVIATIONS"
        assert alt2_state.decision_count == 11

        decisions = {decision.requirement_group_id: decision.decision for decision in review_state.decisions}
        groups = _group_lookup(context)
        assert decisions[groups[("Avdelning 11", frozenset({"Glutenfri"}))]] == ADAPTATION_REQUIRED
        assert decisions[groups[("Avdelning 13", frozenset({"Timbal", "Laktosfri"}))]] == ADAPTATION_REQUIRED
        assert decisions[groups[("Avdelning 16", frozenset({"Glutenfri"}))]] == ADAPTATION_REQUIRED
        assert decisions[groups[("Avdelning 16", frozenset({"Vegetarisk", "Äggfri"}))]] == ADAPTATION_REQUIRED
        assert decisions[groups[("Avdelning 11", frozenset({"Laktosfri"}))]] == NO_ADAPTATION_REQUIRED
        assert decisions[groups[("Avdelning 11", frozenset({"Äggfri"}))]] == NO_ADAPTATION_REQUIRED

        vm = build_product2_page3_vm(
            tenant_id=1,
            site_id=base_seed.SITE_ID,
            service_date=base_seed.SERVICE_DATE,
            meal=base_seed.MEAL,
        )
        assert vm.ready is True
        assert vm.ready_label == "Underlag granskat"
        completion_targets = {target.requirement_group_id: target for target in vm.completion_targets}
        assert len(completion_targets) == 4
        assert completion_targets[groups[("Avdelning 11", frozenset({"Glutenfri"}))]].quantity == 1
        assert completion_targets[groups[("Avdelning 13", frozenset({"Timbal", "Laktosfri"}))]].quantity == 1
        assert completion_targets[groups[("Avdelning 16", frozenset({"Glutenfri"}))]].quantity == 3
        assert completion_targets[groups[("Avdelning 16", frozenset({"Vegetarisk", "Äggfri"}))]].quantity == 1
        assert groups[("Avdelning 11", frozenset({"Laktosfri"}))] not in completion_targets
        assert groups[("Avdelning 11", frozenset({"Äggfri"}))] not in completion_targets


def test_prepare_product2_completion_e2e_is_idempotent(tmp_path, monkeypatch):
    main_db_path = tmp_path / "product2_e2e.db"
    builder_db_path = tmp_path / "product2_e2e_builder.db"

    _seed_temp_base_dataset(monkeypatch, main_db_path, builder_db_path)

    first = prepare_product2_completion_e2e(main_db_path=main_db_path, builder_db_path=builder_db_path)
    second = prepare_product2_completion_e2e(main_db_path=main_db_path, builder_db_path=builder_db_path)

    assert first.completion_targets == second.completion_targets
    assert first.review_decision_count == second.review_decision_count == 6
    assert first.completion_row_count == second.completion_row_count == 0
    assert first.page3_ready is second.page3_ready is True

    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{main_db_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )

    with app.app_context():
        db = get_session()
        try:
            review_rows = int(
                db.execute(
                    text("SELECT COUNT(*) FROM planning_option_reviews WHERE site_id=:site_id AND service_date=:service_date AND meal=:meal"),
                    {"site_id": base_seed.SITE_ID, "service_date": base_seed.SERVICE_DATE, "meal": base_seed.MEAL},
                ).scalar()
                or 0
            )
            decision_rows = int(
                db.execute(
                    text("SELECT COUNT(*) FROM planning_option_review_decisions WHERE tenant_id=:tenant_id"),
                    {"tenant_id": 1},
                ).scalar()
                or 0
            )
            completion_rows = int(
                db.execute(
                    text("SELECT COUNT(*) FROM department_requirement_group_completions WHERE service_date=:service_date AND meal_key=:meal_key"),
                    {"service_date": base_seed.SERVICE_DATE, "meal_key": base_seed.MEAL},
                ).scalar()
                or 0
            )
            assert review_rows == 2
            assert decision_rows == 17
            assert completion_rows == 0
        finally:
            db.close()
