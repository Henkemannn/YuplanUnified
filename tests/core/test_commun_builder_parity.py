from __future__ import annotations

import pytest
from flask import current_app
from sqlalchemy import text

from core.db import get_session
from core.commun_builder_import import import_menu_result_to_builder_canonical
from core.commun_builder_parity import (
    ALLOWED_NON_BLOCKING_WARNINGS,
    CommunBuilderParityDifference,
    CommunBuilderParityEvaluator,
    CommunBuilderParityResult,
)
from core.commun_builder_publication import CommunBuilderPublicationService
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu_service import MenuServiceDB
from core.models import Dish
from tests.core.test_commun_builder_import import _build_flow


def _seed_site_and_department(site_id: str, department_id: str, tenant_id: int = 1) -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tid, 0)"),
            {"id": site_id, "name": "Parity Site", "tid": tenant_id},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                "VALUES(:id, :site_id, :name, 'fixed', 10, 0)"
            ),
            {"id": department_id, "site_id": site_id, "name": "Parity Department"},
        )
        db.commit()
    finally:
        db.close()


def _mark_menu_published(menu_id: int) -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET status='published', updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
            {"id": menu_id},
        )
        db.commit()
    finally:
        db.close()


def _seed_legacy_menu(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    main_text: str,
    alt1_text: str | None = None,
    published: bool = True,
) -> int:
    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id=tenant_id, site_id=site_id, week=week, year=year)

    from core.db import get_new_session

    db = get_new_session()
    try:
        main = Dish(tenant_id=tenant_id, name=main_text, category=None)
        db.add(main)
        if alt1_text is not None:
            alt1 = Dish(tenant_id=tenant_id, name=alt1_text, category=None)
            db.add(alt1)
        db.commit()
        db.refresh(main)
        main_id = main.id
        alt1_id = None
        if alt1_text is not None:
            alt1 = next(item for item in db.query(Dish).filter(Dish.name == alt1_text).all())
            alt1_id = alt1.id
    finally:
        db.close()

    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "main", main_id)
    if alt1_id is not None:
        svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", alt1_id)
    if published:
        _mark_menu_published(menu.id)
    else:
        from core.db import get_session

        db = get_session()
        try:
            db.execute(text("UPDATE menus SET status='draft' WHERE id=:id"), {"id": menu.id})
            db.commit()
        finally:
            db.close()
    return menu.id


def _seed_builder_import(
    *,
    app_session,
    site_id: str,
    year: int,
    week: int,
    items: list[ImportedMenuItem],
) -> tuple[str, int]:
    flow = _build_flow()
    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow
        flow._library_flow.create_composition(composition_id="comp_main", composition_name="Fish Plate")
        flow._library_flow.create_composition(composition_id="comp_alt1", composition_name="Unknown Salad")
        flow._library_flow.create_composition(composition_id="comp_alt2", composition_name="Soup Deluxe")
        from core.menu import create_composition_alias

        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="alias_main",
            composition_id="comp_main",
            alias_text="Fish Plate",
            composition_repository=flow._composition_repository,
        )
        for alias_id, composition_id, alias_text in [
            ("alias_main", "comp_main", "Fish Plate"),
            ("alias_alt2", "comp_alt2", "Soup Deluxe"),
        ]:
            try:
                create_composition_alias(
                    alias_repository=flow._library_flow._alias_repository,
                    alias_id=alias_id,
                    composition_id=composition_id,
                    alias_text=alias_text,
                    composition_repository=flow._composition_repository,
                )
            except ValueError:
                pass
        outcome = import_menu_result_to_builder_canonical(
            MenuImportResult(weeks=[WeekImport(year=year, week=week, items=items)]),
            tenant_id=1,
            site_id=site_id,
        )[0]
        return outcome.menu_id, outcome.builder_menu_version


@pytest.fixture
def parity_app(app_session):
    with app_session.app_context():
        current_app.feature_registry.set("commun.builder.reader_v0", True)
    return app_session


@pytest.fixture(autouse=True)
def _clear_builder_context_after_test(parity_app):
    with parity_app.app_context():
        feature_registry = current_app.feature_registry
        original_reader = feature_registry.enabled("commun.builder.reader_v0") if feature_registry.has("commun.builder.reader_v0") else None
        original_projection_shadow = feature_registry.enabled("commun.builder.projection_shadow_v0") if feature_registry.has("commun.builder.projection_shadow_v0") else None
        original_linkage = feature_registry.enabled("commun.builder.linkage_v0") if feature_registry.has("commun.builder.linkage_v0") else None
        feature_registry.set("commun.builder.projection_shadow_v0", False)
        feature_registry.set("commun.builder.linkage_v0", False)
        db = get_session()
        try:
            for table in [
                "menu_variants",
                "commun_builder_publication_pins",
                "commun_builder_menu_links",
                "menus",
                "dishes",
            ]:
                db.execute(text(f"DELETE FROM {table}"))
            db.commit()
        finally:
            db.close()
    yield
    with parity_app.app_context():
        current_app.extensions.pop("builder_menu_context_flow", None)
        current_app.extensions.pop("commun_builder_projection_reader", None)
        if original_reader is not None:
            current_app.feature_registry.set("commun.builder.reader_v0", original_reader)
        if original_projection_shadow is not None:
            current_app.feature_registry.set("commun.builder.projection_shadow_v0", original_projection_shadow)
        if original_linkage is not None:
            current_app.feature_registry.set("commun.builder.linkage_v0", original_linkage)


def test_parity_inventory_and_runbook(parity_app):
    evaluator = CommunBuilderParityEvaluator()
    inventory = evaluator.get_dependency_inventory()
    assert any(item["feature_flag"] == "commun.builder.reader_v0" for item in inventory)
    assert any(item["function"] == "/ui/weekview_overview" for item in inventory)

    runbook = evaluator.get_rollback_runbook()
    assert runbook["commun.builder.reader_v0"]["disable"] is True
    assert "legacy reader" in runbook["commun.builder.reader_v0"]["fallback"]

    recommendation = evaluator.recommend_next_consumer()
    assert recommendation["route"] == "/ui/admin/menu-import/week/<year>/<week>"
    assert recommendation["consumer"] == "admin menu import week preview"

    prereqs = evaluator.get_retirement_prerequisites()
    assert "legacy_read_path" in prereqs
    assert "legacy_write_path" in prereqs


def _make_gate_result(*, status: str, warnings: list[str], blocking: list[CommunBuilderParityDifference] | None = None) -> CommunBuilderParityResult:
    return CommunBuilderParityResult(
        tenant_id=1,
        site_id="site-gate",
        year=2026,
        week=20,
        legacy_available=True,
        builder_link_available=True,
        publication_pin_available=True,
        builder_projection_available=True,
        legacy_row_count=2,
        builder_row_count=2,
        status=status,
        score=100 if status == "match" else 95,
        go=False,
        reasons=[],
        blocking_differences=list(blocking or []),
        non_blocking_differences=[],
        warnings=warnings,
    )


def test_parity_warning_allowlist_gate(parity_app):
    evaluator = CommunBuilderParityEvaluator()
    allowed_warning = next(iter(ALLOWED_NON_BLOCKING_WARNINGS))

    assert evaluator.get_warning_allowlist() == sorted(ALLOWED_NON_BLOCKING_WARNINGS)

    allowed = _make_gate_result(status="match_with_warnings", warnings=[allowed_warning])
    assert evaluator.gate(allowed).go is True

    unknown = _make_gate_result(status="match_with_warnings", warnings=["unknown_warning_code"])
    assert evaluator.gate(unknown).go is False

    mixed = _make_gate_result(status="match_with_warnings", warnings=[allowed_warning, "unknown_warning_code"])
    assert evaluator.gate(mixed).go is False

    blocker = _make_gate_result(
        status="match_with_warnings",
        warnings=[allowed_warning],
        blocking=[CommunBuilderParityDifference(kind="blocking", blocking=True, detail={"reason": "structural_difference"})],
    )
    assert evaluator.gate(blocker).go is False

    clean = _make_gate_result(status="match", warnings=[])
    assert evaluator.gate(clean).go is True


@pytest.mark.parametrize(
    "setup_name, expected_status, expected_publication_state",
    [
        ("match", "match", "published_current"),
        ("difference", "difference", "published_current"),
        ("no_link", "no_link", "no_link"),
        ("no_pin", "no_pin", "no_pin"),
        ("not_published", "not_published", "not_published"),
        ("version_mismatch", "version_mismatch", "version_mismatch"),
        ("projection_error", "projection_error", "projection_error"),
        ("legacy_only", "legacy_only", "published_current"),
    ],
)
def test_parity_status_matrix(parity_app, monkeypatch, setup_name, expected_status, expected_publication_state):
    tenant_id = 1
    site_id = f"site-{setup_name}"
    department_id = f"dept-{setup_name}"
    year = 2026
    week = 16
    _seed_site_and_department(site_id, department_id, tenant_id=tenant_id)

    evaluator = CommunBuilderParityEvaluator()
    with parity_app.app_context():
        if setup_name == "no_link":
            _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text="Unknown Salad",
                published=True,
            )
        elif setup_name == "no_pin":
            legacy_menu_id = _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text="Unknown Salad",
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
            )
            _mark_menu_published(legacy_menu_id)
        elif setup_name == "not_published":
            _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text=None,
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
            )
        elif setup_name == "version_mismatch":
            legacy_menu_id = _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text=None,
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
            )
            CommunBuilderPublicationService().publish_week(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_menu_id=legacy_menu_id,
            )
            _mark_menu_published(legacy_menu_id)
            from core.db import get_session

            db = get_session()
            try:
                db.execute(
                    text("UPDATE commun_builder_menu_links SET builder_menu_version=2 WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
                    {"tid": tenant_id, "sid": site_id, "year": year, "week": week},
                )
                db.commit()
            finally:
                db.close()
        elif setup_name == "projection_error":
            legacy_menu_id = _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text=None,
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
            )
            CommunBuilderPublicationService().publish_week(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_menu_id=legacy_menu_id,
            )
            _mark_menu_published(legacy_menu_id)
            monkeypatch.setattr(
                "core.commun_builder_parity.get_shadow_projection_reader",
                lambda: (_ for _ in ()).throw(RuntimeError("projection boom")),
            )
        elif setup_name == "legacy_only":
            legacy_menu_id = _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text=None,
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
            )
            CommunBuilderPublicationService().publish_week(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_menu_id=legacy_menu_id,
            )
            _mark_menu_published(legacy_menu_id)
            current_app.feature_registry.set("commun.builder.reader_v0", False)
            result = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
            assert result.status == expected_status
            assert result.publication_state in {"published_current", "legacy_only"}
            assert result.go is False
            return
        else:
            legacy_menu_id = _seed_legacy_menu(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                main_text="Fish Plate",
                alt1_text="Unknown Salad",
                published=False,
            )
            _seed_builder_import(
                app_session=parity_app,
                site_id=site_id,
                year=year,
                week=week,
                items=[
                    ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate"),
                    ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Unknown Salad"),
                ],
            )
            CommunBuilderPublicationService().publish_week(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_menu_id=legacy_menu_id,
            )
            _mark_menu_published(legacy_menu_id)
            if setup_name == "difference":
                from core.db import get_session

                db = get_session()
                try:
                    db.execute(text("UPDATE dishes SET name='Different Fish' WHERE name='Fish Plate'"))
                    db.commit()
                finally:
                    db.close()

        result = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)

    assert result.status == expected_status
    assert result.publication_state == expected_publication_state
    assert result.tenant_id == tenant_id
    assert result.site_id == site_id
    assert result.legacy_available is True
    if setup_name == "no_link":
        assert result.builder_link_available is False
    else:
        assert result.builder_link_available is True
    assert result.publication_pin_available is True or setup_name in {"no_link", "no_pin", "not_published"}
    if setup_name == "match":
        assert result.builder_row_count == result.legacy_row_count
        assert result.go is True
        assert result.status == "match"
        assert result.warnings == []
        assert evaluator.gate(result).go is True
    elif setup_name == "difference":
        assert result.go is False
        assert result.blocking_differences
    elif setup_name == "version_mismatch":
        assert result.go is False
        assert any(diff.kind == "version_mismatch" for diff in result.blocking_differences)
    elif setup_name == "projection_error":
        assert result.go is False
        assert result.publication_state == "projection_error"
    elif setup_name == "no_link":
        assert result.go is False
        assert result.status == "no_link"
    elif setup_name == "no_pin":
        assert result.go is False
        assert result.status == "no_pin"
    elif setup_name == "not_published":
        assert result.go is False
        assert result.status == "not_published"


def test_parity_realistic_transition_flow(parity_app):
    tenant_id = 1
    site_id = "site-transition"
    department_id = "dept-transition"
    year = 2026
    week = 17
    _seed_site_and_department(site_id, department_id, tenant_id=tenant_id)

    with parity_app.app_context():
        current_app.feature_registry.set("commun.builder.reader_v0", True)
        previous_flow = current_app.extensions.get("builder_menu_context_flow")
        try:
            flow = _build_flow()
            current_app.extensions["builder_menu_context_flow"] = flow
            flow._library_flow.create_composition(composition_id="comp_main", composition_name="Fish Plate")
            flow._library_flow.create_composition(composition_id="comp_alt1", composition_name="Unknown Salad")
            flow._library_flow.create_composition(composition_id="comp_alt2", composition_name="Soup Deluxe")
            from core.menu import create_composition_alias

            create_composition_alias(
                alias_repository=flow._library_flow._alias_repository,
                alias_id="alias_main",
                composition_id="comp_main",
                alias_text="Fish Plate",
                composition_repository=flow._composition_repository,
            )
            create_composition_alias(
                alias_repository=flow._library_flow._alias_repository,
                alias_id="alias_alt2",
                composition_id="comp_alt2",
                alias_text="Soup Deluxe",
                composition_repository=flow._composition_repository,
            )

            legacy_menu = MenuServiceDB().create_or_get_menu(tenant_id=tenant_id, site_id=site_id, week=week, year=year)
            from core.db import get_new_session

            db = get_new_session()
            try:
                d1 = Dish(tenant_id=tenant_id, name="Fish Plate", category=None)
                d2 = Dish(tenant_id=tenant_id, name="Unknown Salad", category=None)
                db.add_all([d1, d2])
                db.commit()
                db.refresh(d1)
                db.refresh(d2)
                main_id = d1.id
                alt1_id = d2.id
            finally:
                db.close()

            svc = MenuServiceDB()
            svc.set_variant(tenant_id, legacy_menu.id, "mon", "lunch", "main", main_id)
            svc.set_variant(tenant_id, legacy_menu.id, "mon", "lunch", "alt1", alt1_id)

            v2_outcome = import_menu_result_to_builder_canonical(
                MenuImportResult(
                    weeks=[
                        WeekImport(
                            year=year,
                            week=week,
                            items=[
                                ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate"),
                                ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Unknown Salad"),
                            ],
                        )
                    ]
                ),
                tenant_id=tenant_id,
                site_id=site_id,
            )[0]
            svc.publish_menu(tenant_id=tenant_id, menu_id=legacy_menu.id)
            evaluator = CommunBuilderParityEvaluator()
            v1 = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
            assert v1.status == "match"
            assert v1.publication_state == "published_current"
            assert v1.go is True

            import_menu_result_to_builder_canonical(
                MenuImportResult(
                    weeks=[
                        WeekImport(
                            year=year,
                            week=week,
                            items=[
                                ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate"),
                                ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Soup Deluxe"),
                            ],
                        )
                    ]
                ),
                tenant_id=tenant_id,
                site_id=site_id,
            )[0]
            builder_rows = current_app.extensions["builder_menu_context_flow"].list_menu_rows(v2_outcome.menu_id)
            assert [row["composition_id"] for row in builder_rows] == ["comp_main", "comp_alt2"]
            assert [row["unresolved_text"] for row in builder_rows] == [None, None]
            from core.db import get_session

            db = get_session()
            try:
                pin = db.execute(
                    text("SELECT builder_menu_version FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
                    {"tid": tenant_id, "sid": site_id, "year": year, "week": week},
                ).fetchone()
                link = db.execute(
                    text("SELECT builder_menu_version FROM commun_builder_menu_links WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
                    {"tid": tenant_id, "sid": site_id, "year": year, "week": week},
                ).fetchone()
                assert pin is not None and int(pin[0]) == 1
                assert link is not None and int(link[0]) == 2
            finally:
                db.close()

            mismatch = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
            assert mismatch.status == "version_mismatch"
            assert mismatch.go is False

            alt2 = Dish(tenant_id=tenant_id, name="Soup Deluxe", category=None)
            db = get_new_session()
            try:
                db.add(alt2)
                db.commit()
                db.refresh(alt2)
                svc.set_variant(tenant_id, legacy_menu.id, "mon", "lunch", "alt1", alt2.id)
            finally:
                db.close()

            svc.publish_menu(tenant_id=tenant_id, menu_id=legacy_menu.id)
            match_again = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
            assert match_again.status == "match"
            assert match_again.warnings == []
            assert match_again.non_blocking_differences == []
            assert match_again.publication_state == "published_current"
            assert match_again.go is True
            assert evaluator.gate(match_again).go is True

            svc.unpublish_menu(tenant_id=tenant_id, menu_id=legacy_menu.id)
            unpublished = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
            assert unpublished.status == "not_published"
            assert unpublished.go is False
        finally:
            if previous_flow is None:
                current_app.extensions.pop("builder_menu_context_flow", None)
            else:
                current_app.extensions["builder_menu_context_flow"] = previous_flow


def test_parity_security_and_security_gate(parity_app):
    tenant_id = 1
    site_id = "site-security"
    department_id = "dept-security"
    year = 2026
    week = 18
    _seed_site_and_department(site_id, department_id, tenant_id=tenant_id)

    with parity_app.app_context():
        current_app.feature_registry.set("commun.builder.reader_v0", True)
        _seed_legacy_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            main_text="Fish Plate",
            alt1_text=None,
            published=True,
        )
        _seed_builder_import(
            app_session=parity_app,
            site_id=site_id,
            year=year,
            week=week,
            items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
        )
        evaluator = CommunBuilderParityEvaluator()
        blocked = evaluator.evaluate_week(tenant_id=999, site_id=site_id, year=year, week=week)
        assert blocked.status == "blocked"
        assert blocked.go is False

        wrong_site = evaluator.evaluate_week(tenant_id=tenant_id, site_id="missing-site", year=year, week=week)
        assert wrong_site.status in {"blocked", "no_link"}
        assert wrong_site.go is False

        current_app.feature_registry.set("commun.builder.reader_v0", False)
        legacy_only = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
        assert legacy_only.status == "legacy_only"
        assert legacy_only.go is False
        assert legacy_only.fallback_state == "legacy"


def test_parity_legacy_fallback_failure_blocks(parity_app, monkeypatch):
    tenant_id = 1
    site_id = "site-fallback-failure"
    department_id = "dept-fallback-failure"
    year = 2026
    week = 19
    _seed_site_and_department(site_id, department_id, tenant_id=tenant_id)

    with parity_app.app_context():
        current_app.feature_registry.set("commun.builder.reader_v0", True)
        _seed_legacy_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            main_text="Fish Plate",
            alt1_text=None,
            published=True,
        )
        _seed_builder_import(
            app_session=parity_app,
            site_id=site_id,
            year=year,
            week=week,
            items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate")],
        )

        monkeypatch.setattr(
            "core.commun_builder_parity.current_app.menu_service.get_week_view",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("legacy read failed")),
        )

        evaluator = CommunBuilderParityEvaluator()
        result = evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)

    assert result.status == "blocked"
    assert result.go is False
    assert any(reason.startswith("legacy_unavailable:") for reason in result.reasons)
    assert any(diff.kind == "fallback_failure" for diff in result.blocking_differences)
