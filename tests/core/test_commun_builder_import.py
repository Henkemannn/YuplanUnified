from __future__ import annotations

import pytest
from flask import current_app

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.commun_builder_import import (
    CommunBuilderCanonicalImportError,
    build_canonical_menu_id,
    import_menu_result_to_builder_canonical,
)
from core.commun_builder_publication import CommunBuilderPublicationService
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_projection import CommunBuilderMenuProjectionReader
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu import InMemoryCompositionAliasRepository, MenuService, create_composition_alias


def _build_flow() -> BuilderMenuContextFlow:
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
    )
    return BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )


def _register_flow(app, flow: BuilderMenuContextFlow) -> None:
    with app.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow


def _mixed_import_result() -> MenuImportResult:
    items = [
        ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Fish Plate"),
        ImportedMenuItem(day="monday", meal="lunch", variant_type="alt2", dish_name="Unknown Dish"),
    ]
    return MenuImportResult(weeks=[WeekImport(year=2026, week=16, items=items)])


def test_canonical_menu_id_is_deterministic_and_isolated() -> None:
    first = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=16, import_type="menu")
    second = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=16, import_type="menu")
    other_tenant = build_canonical_menu_id(tenant_id=2, site_id="site-a", year=2026, week=16, import_type="menu")
    other_site = build_canonical_menu_id(tenant_id=1, site_id="site-b", year=2026, week=16, import_type="menu")
    other_week = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=17, import_type="menu")
    other_import = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=16, import_type="xlsx")

    assert first == second
    assert first != other_tenant
    assert first != other_site
    assert first != other_week
    assert first != other_import
    assert "site-a" in first
    assert "2026" in first
    assert "w16" in first


def test_canonical_import_created_unchanged_and_updated(app_session, monkeypatch):
    flow = _build_flow()
    monkeypatch.setattr(CommunBuilderMenuLinkService, "_validate_site_tenant_access", lambda self, tenant_id, site_id: None)

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow

        flow._library_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
        flow._library_flow.create_composition(composition_id="plate_2", composition_name="Soup")
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="alias_1",
            composition_id="plate_1",
            alias_text="Fish Plate",
            composition_repository=flow._composition_repository,
        )
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="alias_2",
            composition_id="plate_2",
            alias_text="Soup",
            composition_repository=flow._composition_repository,
        )

        first = import_menu_result_to_builder_canonical(
            _mixed_import_result(),
            tenant_id=1,
            site_id="site-a",
        )[0]
        assert first.status == "created"
        assert first.builder_menu_version == 1
        assert first.imported_count == 2
        assert first.resolved_count == 1
        assert first.unresolved_count == 1

        menu_id = first.menu_id
        assert flow._menu_service.get_menu(menu_id).version == 1
        assert [row["meal_slot"] for row in flow.list_menu_rows(menu_id)] == ["lunch_alt1", "lunch_alt2"]
        assert flow.list_menu_rows(menu_id)[1]["composition_ref_type"] == "unresolved"
        assert flow.list_menu_rows(menu_id)[1]["unresolved_text"] == "Unknown Dish"

        unchanged = import_menu_result_to_builder_canonical(
            _mixed_import_result(),
            tenant_id=1,
            site_id="site-a",
        )[0]
        assert unchanged.status == "unchanged"
        assert unchanged.builder_menu_version == 1
        assert flow._menu_service.get_menu(menu_id).version == 1
        assert len(flow.list_menu_rows(menu_id)) == 2

        changed_result = MenuImportResult(
            weeks=[
                WeekImport(
                    year=2026,
                    week=16,
                    items=[
                        ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Soup"),
                        ImportedMenuItem(day="tuesday", meal="dinner", variant_type="main", dish_name="Fish Plate"),
                    ],
                )
            ]
        )
        updated = import_menu_result_to_builder_canonical(
            changed_result,
            tenant_id=1,
            site_id="site-a",
        )[0]
        assert updated.status == "updated"
        assert updated.builder_menu_version == 2
        assert flow._menu_service.get_menu(menu_id).version == 2
        assert [row["day"] for row in flow.list_menu_rows(menu_id)] == ["monday", "tuesday"]
        assert flow.list_menu_rows(menu_id)[0]["composition_id"] == "plate_2"
        assert flow.list_menu_rows(menu_id)[1]["composition_id"] == "plate_1"


def test_canonical_import_rolls_back_builder_failure(app_session, monkeypatch):
    flow = _build_flow()
    monkeypatch.setattr(CommunBuilderMenuLinkService, "_validate_site_tenant_access", lambda self, tenant_id, site_id: None)

    def boom(*args, **kwargs):
        raise RuntimeError("builder write failed")

    monkeypatch.setattr(flow._menu_service, "add_menu_detail", boom)

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow
        with pytest.raises(CommunBuilderCanonicalImportError):
            import_menu_result_to_builder_canonical(
                MenuImportResult(
                    weeks=[
                        WeekImport(
                            year=2026,
                            week=18,
                            items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Fish Plate")],
                        )
                    ]
                ),
                tenant_id=1,
                site_id="site-a",
            )

        menu_id = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=18, import_type="menu")
        assert flow._menu_service.get_menu(menu_id) is None


def test_canonical_import_rolls_back_linkage_failure(app_session, monkeypatch):
    flow = _build_flow()
    monkeypatch.setattr(CommunBuilderMenuLinkService, "_validate_site_tenant_access", lambda self, tenant_id, site_id: None)

    flow._library_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    create_composition_alias(
        alias_repository=flow._library_flow._alias_repository,
        alias_id="alias_1",
        composition_id="plate_1",
        alias_text="Fish Plate",
        composition_repository=flow._composition_repository,
    )

    monkeypatch.setattr(
        CommunBuilderMenuLinkService,
        "create_or_replace_link",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("linkage failed")),
    )

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow
        with pytest.raises(CommunBuilderCanonicalImportError):
            import_menu_result_to_builder_canonical(
                MenuImportResult(
                    weeks=[
                        WeekImport(
                            year=2026,
                            week=19,
                            items=[ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Fish Plate")],
                        )
                    ]
                ),
                tenant_id=1,
                site_id="site-a",
            )

        menu_id = build_canonical_menu_id(tenant_id=1, site_id="site-a", year=2026, week=19, import_type="menu")
        assert flow._menu_service.get_menu(menu_id) is None


def test_canonical_import_end_to_end_projection_roundtrip(app_session, monkeypatch):
    flow = _build_flow()
    monkeypatch.setattr(CommunBuilderMenuLinkService, "_validate_site_tenant_access", lambda self, tenant_id, site_id: None)

    with app_session.app_context():
        current_app.extensions["builder_menu_context_flow"] = flow

        flow._library_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
        flow._library_flow.create_composition(composition_id="plate_2", composition_name="Soup")
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="alias_1",
            composition_id="plate_1",
            alias_text="Fish Plate",
            composition_repository=flow._composition_repository,
        )
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="alias_2",
            composition_id="plate_2",
            alias_text="Soup",
            composition_repository=flow._composition_repository,
        )

        result = MenuImportResult(
            weeks=[
                WeekImport(
                    year=2026,
                    week=21,
                    items=[
                        ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate"),
                        ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Unknown Salad"),
                        ImportedMenuItem(day="tuesday", meal="dinner", variant_type="main", dish_name="Soup"),
                    ],
                )
            ]
        )

        outcomes = import_menu_result_to_builder_canonical(result, tenant_id=1, site_id="site-a")
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.status == "created"
        assert outcome.builder_menu_version == 1
        assert outcome.imported_count == 3
        assert outcome.resolved_count == 2
        assert outcome.unresolved_count == 1

        menu_id = outcome.menu_id
        rows = flow.list_menu_rows(menu_id)
        assert [row["meal_slot"] for row in rows] == ["lunch_main", "lunch_alt1", "dinner_main"]
        assert rows[0]["composition_id"] == "plate_1"
        assert rows[1]["composition_id"] is None
        assert rows[1]["unresolved_text"] == "Unknown Salad"
        assert rows[2]["composition_id"] == "plate_2"

        projection = CommunBuilderMenuProjectionReader().get_projection(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
        )
        assert projection.status == "ok"
        assert projection.projection is not None
        assert projection.projection.builder_menu_id == menu_id
        assert projection.projection.builder_menu_version == 1
        assert [(row.day, row.meal, row.variant_type) for row in projection.projection.rows] == [
            ("monday", "lunch", "main"),
            ("monday", "lunch", "alt1"),
            ("tuesday", "dinner", "main"),
        ]
        assert [row.text for row in projection.projection.rows] == ["Fish Plate", "Unknown Salad", "Soup"]
        assert [row.composition_id for row in projection.projection.rows] == ["plate_1", None, "plate_2"]

        comparison = CommunBuilderMenuProjectionReader().compare_with_legacy(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
            legacy_weekview={
                "rows": [
                    {"day": "monday", "meal": "lunch", "variant_type": "main", "sort_order": 10, "text": "Fish Plate"},
                    {"day": "monday", "meal": "lunch", "variant_type": "alt1", "sort_order": 20, "text": "Unknown Salad"},
                    {"day": "tuesday", "meal": "dinner", "variant_type": "main", "sort_order": 30, "text": "Soup"},
                ]
            },
        )
        assert comparison.status == "match"
        assert comparison.difference_count == 0

        publication_service = CommunBuilderPublicationService()
        publication_service.publish_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
            legacy_menu_id=None,
        )
        publication = publication_service.get_publication_for_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
        )
        assert publication is not None
        assert publication.builder_menu_version == 1

        updated_result = MenuImportResult(
            weeks=[
                WeekImport(
                    year=2026,
                    week=21,
                    items=[
                        ImportedMenuItem(day="monday", meal="lunch", variant_type="main", dish_name="Fish Plate"),
                        ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name="Unknown Salad"),
                        ImportedMenuItem(day="tuesday", meal="dinner", variant_type="main", dish_name="Soup Deluxe"),
                    ],
                )
            ]
        )
        updated_outcome = import_menu_result_to_builder_canonical(updated_result, tenant_id=1, site_id="site-a")[0]
        assert updated_outcome.status == "updated"
        assert updated_outcome.builder_menu_version == 2

        link_after_update = CommunBuilderMenuLinkService().get_link_for_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
        )
        assert link_after_update is not None
        assert int(link_after_update.builder_menu_version) == 2

        publication_after_update = publication_service.get_publication_for_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
        )
        assert publication_after_update is not None
        assert publication_after_update.builder_menu_version == 1

        pinned_projection = CommunBuilderMenuProjectionReader().get_projection_for_pinned_menu(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
            builder_menu_id=publication_after_update.builder_menu_id,
            builder_menu_version=publication_after_update.builder_menu_version,
        )
        assert pinned_projection.status == "version_mismatch"

        publication_service.republish_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
            legacy_menu_id=None,
        )
        republished = publication_service.get_publication_for_week(
            tenant_id=1,
            site_id="site-a",
            year=2026,
            week=21,
        )
        assert republished is not None
        assert republished.builder_menu_version == 2
