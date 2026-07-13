from __future__ import annotations

import pytest
from flask import current_app, g
from sqlalchemy import text

from core.admin_repo import SitesRepo
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_projection import (
    CommunBuilderMenuProjectionReader,
    _normalize_builder_meal_slot,
)
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
from core.menu import ImportedMenuRow, InMemoryCompositionAliasRepository, MenuService
from core.models import Dish, Tenant


def _build_builder_menu_context_flow() -> tuple[BuilderMenuContextFlow, CompositionService, InMemoryCompositionRepository]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)
    menu_service = MenuService(composition_repository=composition_repository)
    builder_flow = BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=InMemoryComponentAliasRepository(),
    )

    builder_flow = BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return builder_flow, composition_service, composition_repository


_SITE_SEQUENCE = 0


def _seed_tenant_and_site(app_session):
    global _SITE_SEQUENCE
    with app_session.app_context():
        db = get_session()
        try:
            tenant = db.query(Tenant).first()
            if tenant is None:
                tenant = Tenant(name="ProjectionTenant")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
            tenant_id = int(tenant.id)
        finally:
            db.close()
            _SITE_SEQUENCE += 1
            site, _ = SitesRepo().create_site(f"Projection Site {_SITE_SEQUENCE}", tenant_id=tenant_id)
            return tenant_id, site["id"]


def _create_legacy_menu_rows(tenant_id: int, site_id: str, year: int, week: int, rows: list[tuple[str, str, str, str]]) -> int:
    db = get_session()
    try:
        dish_ids: dict[str, int] = {}
        for dish_name in sorted({dish_name for _, _, _, dish_name in rows}):
            dish = Dish(tenant_id=tenant_id, name=dish_name)
            db.add(dish)
            db.commit()
            db.refresh(dish)
            dish_ids[dish_name] = int(dish.id)
        menu = current_app.menu_service.create_or_get_menu(tenant_id, site_id, week, year)
        for day, meal, variant_type, dish_name in rows:
            current_app.menu_service.set_variant(
                tenant_id,
                int(menu.id),
                day,
                meal,
                variant_type,
                dish_ids[dish_name],
            )
        return int(menu.id)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _restore_projection_test_state(app_session):
    with app_session.app_context():
        feature_registry = current_app.feature_registry
        feature_registry.set("commun.builder.projection_shadow_v0", False)
        feature_registry.set("commun.builder.linkage_v0", False)
        current_app.extensions.pop("builder_menu_context_flow", None)
        current_app.extensions.pop("commun_builder_projection_reader", None)
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
    with app_session.app_context():
        current_app.extensions.pop("builder_menu_context_flow", None)
        current_app.extensions.pop("commun_builder_projection_reader", None)
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)
        current_app.feature_registry.set("commun.builder.linkage_v0", False)


def test_projection_reader_explicit_slots_map_directly(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, composition_repo = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        composition_service.create_composition(composition_id="comp_2", composition_name="Soup")
        composition_service.create_composition(composition_id="comp_3", composition_name="Cake")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_main",
            composition_id="comp_1",
            sort_order=10,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt2",
            composition_id="comp_2",
            sort_order=20,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="tuesday",
            meal_slot="dinner_main",
            composition_id="comp_3",
            sort_order=30,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )

        reader = CommunBuilderMenuProjectionReader()
        result = reader.get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)

    assert result.status == "ok"
    assert result.projection is not None
    assert result.projection.builder_menu_id == "builder-menu-1"
    assert result.projection.builder_menu_version == 1
    assert [(row.day, row.meal, row.variant_type) for row in result.projection.rows] == [
        ("monday", "lunch", "main"),
        ("monday", "lunch", "alt2"),
        ("tuesday", "dinner", "main"),
    ]
    assert [row.builder_menu_row_id for row in result.projection.rows] == [
        "builder-menu-1-row-1",
        "builder-menu-1-row-2",
        "builder-menu-1-row-3",
    ]
    assert [row.text for row in result.projection.rows] == ["Fish Plate", "Soup", "Cake"]
    assert all(row.error is None for row in result.projection.rows)


def test_projection_reader_generic_meal_slots_remain_unresolved(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch",
            composition_id="comp_1",
            sort_order=10,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        result = CommunBuilderMenuProjectionReader().get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)

    assert result.status == "projection_error"
    assert result.error == "variant_mapping_missing"
    assert result.projection is not None
    assert result.projection.rows[0].variant_type == "unresolved_variant"
    assert result.projection.rows[0].builder_menu_row_id == "builder-menu-1-row-1"
    assert result.projection.rows[0].text == "Fish Plate"


def test_projection_reader_generic_meal_rows_do_not_infer_alt_positions(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        composition_service.create_composition(composition_id="comp_2", composition_name="Soup")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch",
            composition_id="comp_1",
            sort_order=10,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch",
            composition_id="comp_2",
            sort_order=20,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        result = CommunBuilderMenuProjectionReader().get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)

    assert result.status == "projection_error"
    assert result.error == "variant_mapping_missing"
    assert [row.variant_type for row in result.projection.rows] == ["unresolved_variant", "unresolved_variant"]


def test_projection_reader_rejects_unknown_meal_slot():
    with pytest.raises(ValueError, match="unknown meal slot"):
        _normalize_builder_meal_slot("snack")


def test_projection_reader_reports_no_link_and_version_mismatch(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
               meal_slot="lunch_alt1",
            composition_id="comp_1",
        )
        reader = CommunBuilderMenuProjectionReader()
        no_link = reader.get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)
        assert no_link.status == "no_link"

        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        mismatch_menu = builder_flow._menu_service.get_menu("builder-menu-1")
        assert mismatch_menu is not None
        builder_flow._menu_service._menu_repository.update(  # type: ignore[attr-defined]
            type(mismatch_menu)(
                menu_id=mismatch_menu.menu_id,
                title=mismatch_menu.title,
                site_id=mismatch_menu.site_id,
                week_key=mismatch_menu.week_key,
                version=2,
                status=mismatch_menu.status,
            )
        )

        mismatch = reader.get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)

    assert mismatch.status == "version_mismatch"
    assert mismatch.linked_version == 1
    assert mismatch.current_version == 2


def test_projection_reader_marks_missing_composition_as_projection_error(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, composition_repo = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
        )
        composition_repo._compositions.pop("comp_1")  # type: ignore[attr-defined]
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        reader = CommunBuilderMenuProjectionReader()
        result = reader.get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)

    assert result.status == "projection_error"
    assert result.error == "composition_missing"
    assert result.projection is not None
    assert result.projection.rows[0].resolved is False
    assert result.projection.rows[0].composition_id is None


def test_projection_reader_rejects_unknown_explicit_variant_suffix(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt9",
            composition_id="comp_1",
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        with pytest.raises(ValueError, match="unknown variant slot: lunch_alt9"):
            CommunBuilderMenuProjectionReader().get_projection(tenant_id=tenant_id, site_id=site_id, year=2026, week=16)


def test_week_view_shadow_flag_off_does_not_touch_shadow_path(app_session, monkeypatch):
    tenant_id, site_id = _seed_tenant_and_site(app_session)

    with app_session.app_context():
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)
        _create_legacy_menu_rows(
            tenant_id,
            site_id,
            2026,
            16,
            [("monday", "lunch", "alt1", "Fish Plate")],
        )
        baseline = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)

        monkeypatch.setattr(
            "core.commun_builder_projection.get_shadow_projection_reader",
            lambda: pytest.fail("shadow reader should not be invoked when flag is off"),
        )
        monkeypatch.setattr(
            "core.commun_builder_linkage.CommunBuilderMenuLinkService.get_link_for_week",
            lambda *args, **kwargs: pytest.fail("linkage service should not be invoked when flag is off"),
        )

        result = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)

    assert result == baseline


@pytest.mark.parametrize("case", ["full_match", "no_link", "version_mismatch", "missing_composition"])
def test_week_view_shadow_mode_preserves_legacy_response_for_shadow_states(app_session, case):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, composition_repo = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", True)
        try:
            _create_legacy_menu_rows(
                tenant_id,
                site_id,
                2026,
                16,
                [
                    ("monday", "lunch", "alt1", "Fish Plate"),
                    ("monday", "lunch", "alt2", "Unknown dish"),
                ],
            )
            baseline = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)

            builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1, status="published")
            composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
            builder_flow.add_composition_menu_row(
                menu_id="builder-menu-1",
                day="monday",
                meal_slot="lunch_alt1",
                composition_id="comp_1",
                sort_order=10,
            )
            builder_flow.import_menu_rows(
                menu_id="builder-menu-1",
                rows=[ImportedMenuRow(day="monday", meal_slot="lunch_alt2", raw_text="Unknown dish", sort_order=20)],
            )

            if case in ("full_match", "version_mismatch", "missing_composition"):
                CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=2026,
                    week=16,
                    builder_menu_id="builder-menu-1",
                    source="manual",
                )
            if case == "version_mismatch":
                menu = builder_flow._menu_service.get_menu("builder-menu-1")
                assert menu is not None
                builder_flow._menu_service._menu_repository.update(  # type: ignore[attr-defined]
                    type(menu)(
                        menu_id=menu.menu_id,
                        title=menu.title,
                        site_id=menu.site_id,
                        week_key=menu.week_key,
                        version=2,
                        status=menu.status,
                    )
                )
            if case == "missing_composition":
                composition_repo._compositions.pop("comp_1")  # type: ignore[attr-defined]

            result = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)
        finally:
            current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)

    assert result == baseline


def test_week_view_shadow_mode_duplicate_rows_are_preserved(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", True)
        try:
            builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1, status="published")
            composition_service.create_composition(composition_id="comp_1", composition_name="Soup")
            composition_service.create_composition(composition_id="comp_2", composition_name="Bread")
            builder_flow.add_composition_menu_row(
                menu_id="builder-menu-1",
                day="monday",
                meal_slot="lunch_alt1",
                composition_id="comp_1",
                sort_order=10,
            )
            builder_flow.add_composition_menu_row(
                menu_id="builder-menu-1",
                day="monday",
                meal_slot="lunch_alt1",
                composition_id="comp_2",
                sort_order=20,
            )
            CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
                tenant_id=tenant_id,
                site_id=site_id,
                year=2026,
                week=16,
                builder_menu_id="builder-menu-1",
                source="manual",
            )

            shadow = {
                "rows": [
                    {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 10, "text": "Soup"},
                    {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 20, "text": "Bread"},
                ]
            }
            comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
                tenant_id=tenant_id,
                site_id=site_id,
                year=2026,
                week=16,
                legacy_weekview=shadow,
            )
        finally:
            current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)

    assert comparison.status == "match"
    assert comparison.legacy_row_count == 2
    assert comparison.builder_row_count == 2


def test_projection_reader_duplicate_comparison_detects_missing_in_legacy(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Soup")
        composition_service.create_composition(composition_id="comp_2", composition_name="Bread")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
            sort_order=10,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_2",
            sort_order=20,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        _create_legacy_menu_rows(
            tenant_id,
            site_id,
            2026,
            16,
            [("monday", "lunch", "alt1", "Soup")],
        )
        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            legacy_weekview=current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026),
        )

    assert comparison.status == "difference"
    assert comparison.missing_in_legacy
    assert len(comparison.missing_in_legacy) == 1


def test_projection_reader_duplicate_comparison_detects_missing_in_builder(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Soup")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
            sort_order=10,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        legacy_weekview = {
            "rows": [
                {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 10, "text": "Soup"},
                {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 20, "text": "Bread"},
            ]
        }
        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            legacy_weekview=legacy_weekview,
        )

    assert comparison.status == "difference"
    assert comparison.missing_in_builder
    assert len(comparison.missing_in_builder) == 1


def test_projection_reader_duplicate_comparison_detects_order_mismatch(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Soup")
        composition_service.create_composition(composition_id="comp_2", composition_name="Bread")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
            sort_order=20,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_2",
            sort_order=10,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        _create_legacy_menu_rows(
            tenant_id,
            site_id,
            2026,
            16,
            [
                ("monday", "lunch", "alt1", "Soup"),
                ("monday", "lunch", "alt1", "Bread"),
            ],
        )
        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            legacy_weekview=current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026),
        )

    assert comparison.status == "difference"
    assert comparison.order_mismatches


def test_projection_reader_duplicate_comparison_preserves_duplicate_rows(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Soup")
        composition_service.create_composition(composition_id="comp_2", composition_name="Bread")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
            sort_order=10,
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_2",
            sort_order=10,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        legacy_rows = {
            "rows": [
                {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 10, "text": "Soup"},
                {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 10, "text": "Bread"},
            ]
        }
        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            legacy_weekview=legacy_rows,
        )

    assert comparison.status == "match"
    assert comparison.legacy_row_count == 2
    assert comparison.builder_row_count == 2


@pytest.mark.parametrize("mode", ["reader_exception", "comparison_exception"])
def test_week_view_shadow_mode_preserves_legacy_response_on_shadow_exceptions(app_session, monkeypatch, caplog, mode):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", True)
        try:
            _create_legacy_menu_rows(
                tenant_id,
                site_id,
                2026,
                16,
                [("monday", "lunch", "alt1", "Fish Plate")],
            )
            baseline = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)

            builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
            composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
            builder_flow.add_composition_menu_row(
                menu_id="builder-menu-1",
                day="monday",
                meal_slot="lunch_alt1",
                composition_id="comp_1",
            )
            CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
                tenant_id=tenant_id,
                site_id=site_id,
                year=2026,
                week=16,
                builder_menu_id="builder-menu-1",
                source="manual",
            )

            if mode == "reader_exception":
                monkeypatch.setattr(
                    "core.commun_builder_projection.get_shadow_projection_reader",
                    lambda: (_ for _ in ()).throw(RuntimeError("reader boom")),
                )
            else:
                class _ExplodingReader:
                    def compare_with_legacy(self, **kwargs):
                        raise RuntimeError("comparison boom")

                monkeypatch.setattr(
                    "core.commun_builder_projection.get_shadow_projection_reader",
                    lambda: _ExplodingReader(),
                )

            caplog.clear()
            result = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)
        finally:
            current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)

    assert result == baseline
    assert any("commun_builder_projection_shadow_error" in record.getMessage() for record in caplog.records)


def test_feature_flag_override_resolver_prefers_tenant_context(app_session):
    with app_session.app_context():
        current_app.feature_registry.set("commun.builder.linkage_v0", False)
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)
        g.tenant_feature_flags = {
            "commun.builder.projection_shadow_v0": True,
            "commun.builder.linkage_v0": False,
        }

        assert current_app.feature_enabled("commun.builder.projection_shadow_v0") is True
        assert current_app.feature_enabled("commun.builder.linkage_v0") is False


def test_shadow_mode_preserves_legacy_response_and_records_comparison(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.feature_registry.set("commun.builder.projection_shadow_v0", True)
        try:
            builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1, status="published")
            composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
            builder_flow.add_composition_menu_row(
                menu_id="builder-menu-1",
                day="monday",
                meal_slot="lunch_alt1",
                composition_id="comp_1",
                sort_order=10,
            )
            builder_flow.import_menu_rows(
                menu_id="builder-menu-1",
                rows=[ImportedMenuRow(day="monday", meal_slot="lunch_alt2", raw_text="Unknown dish", sort_order=20)],
            )
            CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
                tenant_id=tenant_id,
                site_id=site_id,
                year=2026,
                week=16,
                builder_menu_id="builder-menu-1",
                source="manual",
            )

            legacy_menu_id = _create_legacy_menu_rows(
                tenant_id,
                site_id,
                2026,
                16,
                [
                    ("monday", "lunch", "alt1", "Fish Plate"),
                    ("monday", "lunch", "alt2", "Unknown dish"),
                ],
            )
            legacy_before = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)
            legacy_after = current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026)
            shadow = getattr(g, "commun_builder_projection_shadow", None)
        finally:
            current_app.feature_registry.set("commun.builder.projection_shadow_v0", False)

    assert legacy_before == legacy_after
    assert legacy_before["menu_id"] == legacy_menu_id
    assert shadow is not None
    assert shadow.status == "match"
    assert shadow.legacy_row_count == 2
    assert shadow.builder_row_count == 2


def test_comparison_reports_text_and_order_differences(app_session):
    tenant_id, site_id = _seed_tenant_and_site(app_session)
    builder_flow, composition_service, _ = _build_builder_menu_context_flow()

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-1", site_id=site_id, week_key="2026-W16", version=1)
        composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-1",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_1",
            sort_order=20,
        )
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            builder_menu_id="builder-menu-1",
            source="manual",
        )
        _create_legacy_menu_rows(
            tenant_id,
            site_id,
            2026,
            16,
            [("monday", "lunch", "alt1", "Different Name")],
        )

        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=tenant_id,
            site_id=site_id,
            year=2026,
            week=16,
            legacy_weekview=current_app.menu_service.get_week_view(tenant_id, site_id, 16, 2026),
        )

    assert comparison.status == "difference"
    assert comparison.legacy_row_count >= 1
    assert comparison.builder_row_count == 1
    assert comparison.text_mismatches
    assert comparison.order_mismatches