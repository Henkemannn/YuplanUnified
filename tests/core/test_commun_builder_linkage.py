from __future__ import annotations

import pytest

from core.admin_repo import SitesRepo
from core.builder import BuilderFlow
from core.commun_builder_linkage import CommunBuilderMenuLinkService
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
from core.models import CommunBuilderMenuLink, Menu, Tenant
from core.builder_menu_context_flow import BuilderMenuContextFlow
from sqlalchemy import text


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
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return menu_context_flow, composition_service, composition_repository


def _seed_tenants_and_sites(app_session):
    with app_session.app_context():
        db = get_session()
        try:
            tenant_1 = db.query(Tenant).filter_by(name="Tenant 1").one_or_none()
            if tenant_1 is None:
                tenant_1 = Tenant(name="Tenant 1")
                db.add(tenant_1)
                db.commit()
                db.refresh(tenant_1)

            tenant_2 = db.query(Tenant).filter_by(name="Tenant 2").one_or_none()
            if tenant_2 is None:
                tenant_2 = Tenant(name="Tenant 2")
                db.add(tenant_2)
                db.commit()
                db.refresh(tenant_2)
            tenant_1_id = int(tenant_1.id)
            tenant_2_id = int(tenant_2.id)
        finally:
            db.close()

        site_repo = SitesRepo()
        site_1, _ = site_repo.create_site("Site 1", tenant_id=tenant_1_id)
        site_2, _ = site_repo.create_site("Site 2", tenant_id=tenant_1_id)
        site_3, _ = site_repo.create_site("Site 3", tenant_id=tenant_2_id)
    return tenant_1_id, tenant_2_id, site_1["id"], site_2["id"], site_3["id"]


def _seed_legacy_menu(site_id: str, tenant_id: int, year: int, week: int) -> int:
    db = get_session()
    try:
        legacy_menu = Menu(tenant_id=tenant_id, site_id=site_id, year=year, week=week, status="draft")
        db.add(legacy_menu)
        db.commit()
        db.refresh(legacy_menu)
        return int(legacy_menu.id)
    finally:
        db.close()


def test_create_or_replace_link_happy_path_and_round_trip(app_session):
    tenant_1, _, site_1, _, _ = _seed_tenants_and_sites(app_session)
    menu_context_flow, composition_service, _ = _build_builder_menu_context_flow()
    year, week = 2026, 28
    builder_menu = menu_context_flow.create_menu(
        menu_id="builder-menu-1",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
        version=3,
    )
    composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
    menu_context_flow.add_composition_menu_row(
        menu_id="builder-menu-1",
        day="monday",
        meal_slot="lunch",
        composition_id="comp_1",
        sort_order=10,
    )
    menu_context_flow.import_menu_rows(
        menu_id="builder-menu-1",
        rows=[ImportedMenuRow(day="tuesday", meal_slot="dinner", raw_text="Unknown dish")],
    )
    legacy_menu_id = _seed_legacy_menu(site_1, tenant_1, year, week)

    service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
    link = service.create_or_replace_link(
        tenant_id=tenant_1,
        site_id=site_1,
        year=year,
        week=week,
        builder_menu_id=builder_menu.menu_id,
        legacy_menu_id=legacy_menu_id,
        source="manual",
    )

    assert link.tenant_id == tenant_1
    assert link.site_id == site_1
    assert link.year == year
    assert link.week == week
    assert link.legacy_menu_id == legacy_menu_id
    assert link.builder_menu_id == "builder-menu-1"
    assert link.builder_menu_version == 3
    assert link.source == "manual"
    assert link.projection_version == 1

    round_trip = service.get_link_for_week(tenant_id=tenant_1, site_id=site_1, year=year, week=week)
    assert round_trip is not None
    assert round_trip.id == link.id


def test_create_or_replace_link_updates_existing_row_instead_of_duplicate(app_session):
    tenant_1, _, site_1, _, _ = _seed_tenants_and_sites(app_session)
    menu_context_flow, _, _ = _build_builder_menu_context_flow()
    year, week = 2026, 29
    first_menu = menu_context_flow.create_menu(
        menu_id="builder-menu-1",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
        version=1,
    )
    second_menu = menu_context_flow.create_menu(
        menu_id="builder-menu-2",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
        version=4,
    )

    service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
    first_link = service.create_or_replace_link(
        tenant_id=tenant_1,
        site_id=site_1,
        year=year,
        week=week,
        builder_menu_id=first_menu.menu_id,
        source="manual",
    )
    second_link = service.create_or_replace_link(
        tenant_id=tenant_1,
        site_id=site_1,
        year=year,
        week=week,
        builder_menu_id=second_menu.menu_id,
        source="pilot",
    )

    assert second_link.id == first_link.id
    assert second_link.builder_menu_id == second_menu.menu_id
    assert second_link.builder_menu_version == 4
    assert second_link.source == "pilot"

    db = get_session()
    try:
        rows = db.query(CommunBuilderMenuLink).filter_by(tenant_id=tenant_1, site_id=site_1, year=year, week=week).all()
        assert len(rows) == 1
    finally:
        db.close()


def test_create_or_replace_link_accepts_builder_menu_with_mixed_rows(app_session):
    tenant_1, _, site_1, _, _ = _seed_tenants_and_sites(app_session)
    menu_context_flow, composition_service, _ = _build_builder_menu_context_flow()
    year, week = 2026, 30
    builder_menu = menu_context_flow.create_menu(
        menu_id="builder-menu-1",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
    )
    composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
    menu_context_flow.add_composition_menu_row(
        menu_id="builder-menu-1",
        day="monday",
        meal_slot="lunch",
        composition_id="comp_1",
        sort_order=10,
    )
    menu_context_flow.import_menu_rows(
        menu_id="builder-menu-1",
        rows=[ImportedMenuRow(day="monday", meal_slot="dinner", raw_text="Stekt fisk med kall sås och potatis")],
    )

    service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
    link = service.create_or_replace_link(
        tenant_id=tenant_1,
        site_id=site_1,
        year=year,
        week=week,
        builder_menu_id=builder_menu.menu_id,
        source="import",
    )

    assert link.builder_menu_id == builder_menu.menu_id
    assert link.source == "import"


def test_create_or_replace_link_rejects_invalid_tenant_site_and_menu_combinations(app_session):
    tenant_1, tenant_2, site_1, site_2, site_3 = _seed_tenants_and_sites(app_session)
    menu_context_flow, _, _ = _build_builder_menu_context_flow()
    year, week = 2026, 31
    builder_site_1_menu = menu_context_flow.create_menu(
        menu_id="builder-site-1",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
    )
    builder_site_2_menu = menu_context_flow.create_menu(
        menu_id="builder-site-2",
        site_id=site_2,
        week_key=f"{year}-W{week:02d}",
    )
    service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)

    with pytest.raises(ValueError, match="site_not_found_or_not_owned"):
        service.create_or_replace_link(
            tenant_id=tenant_2,
            site_id=site_1,
            year=year,
            week=week,
            builder_menu_id=builder_site_1_menu.menu_id,
        )

    with pytest.raises(ValueError, match="builder_menu_site_mismatch"):
        service.create_or_replace_link(
            tenant_id=tenant_1,
            site_id=site_1,
            year=year,
            week=week,
            builder_menu_id=builder_site_2_menu.menu_id,
        )

    with pytest.raises(ValueError, match="builder_menu_not_found"):
        service.create_or_replace_link(
            tenant_id=tenant_1,
            site_id=site_1,
            year=year,
            week=week,
            builder_menu_id="missing-builder-menu",
        )

    with pytest.raises(ValueError, match="legacy_menu_tenant_mismatch"):
        legacy_menu_id = _seed_legacy_menu(site_3, tenant_2, year, week)
        service.create_or_replace_link(
            tenant_id=tenant_1,
            site_id=site_1,
            year=year,
            week=week,
            builder_menu_id=builder_site_1_menu.menu_id,
            legacy_menu_id=legacy_menu_id,
        )


def test_delete_link_removes_only_link_row(app_session):
    tenant_1, _, site_1, _, _ = _seed_tenants_and_sites(app_session)
    menu_context_flow, composition_service, _ = _build_builder_menu_context_flow()
    year, week = 2026, 32
    builder_menu = menu_context_flow.create_menu(
        menu_id="builder-menu-1",
        site_id=site_1,
        week_key=f"{year}-W{week:02d}",
    )
    composition_service.create_composition(composition_id="comp_1", composition_name="Fish Plate")
    menu_context_flow.add_composition_menu_row(
        menu_id="builder-menu-1",
        day="monday",
        meal_slot="lunch",
        composition_id="comp_1",
    )
    legacy_menu_id = _seed_legacy_menu(site_1, tenant_1, year, week)

    service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
    link = service.create_or_replace_link(
        tenant_id=tenant_1,
        site_id=site_1,
        year=year,
        week=week,
        builder_menu_id=builder_menu.menu_id,
        legacy_menu_id=legacy_menu_id,
        source="manual",
    )

    removed = service.delete_link(tenant_id=tenant_1, site_id=site_1, year=year, week=week)
    assert removed is True
    assert service.get_link_for_week(tenant_id=tenant_1, site_id=site_1, year=year, week=week) is None

    db = get_session()
    try:
        legacy_menu = db.execute(text("SELECT id FROM menus WHERE id=:id"), {"id": legacy_menu_id}).fetchone()
        assert legacy_menu is not None
        assert db.query(CommunBuilderMenuLink).filter_by(id=link.id).one_or_none() is None
    finally:
        db.close()