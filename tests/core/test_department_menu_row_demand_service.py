from __future__ import annotations

from flask import current_app
import pytest
from sqlalchemy import text

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_publication import CommunBuilderPublicationService
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
from core.department_menu_row_demand_repo import DepartmentMenuRowDemandRepo
from core.department_menu_row_demand_service import DepartmentMenuRowDemandError, DepartmentMenuRowDemandService
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB
from core.models import Department, Site, Tenant


def _seed_site(app_session, *, site_id: str, tenant_id: int = 1) -> None:
    db = get_new_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"),
            {"id": site_id, "name": "Demand Site", "tenant_id": tenant_id},
        )
        db.commit()
    finally:
        db.close()


def _seed_department(app_session, *, site_id: str, department_id: str, tenant_name: str | None = None) -> tuple[int, str, str]:
    tenant_name = tenant_name or f"DemandTenant-{site_id}"
    db = get_session()
    try:
        tenant = db.get(Tenant, 1)
        if tenant is None:
            tenant = Tenant(id=1, name=tenant_name)
            db.add(tenant)
        else:
            tenant.name = tenant_name
        site = db.get(Site, site_id)
        if site is None:
            site = Site(id=site_id, name="Demand Site", tenant_id=1, version=0)
            db.add(site)
        department = db.get(Department, department_id)
        if department is None:
            department = Department(
                id=department_id,
                site_id=site_id,
                name="Demand Department",
                resident_count_mode="manual",
                resident_count_fixed=10,
            )
            db.add(department)
        db.commit()
        return 1, str(site.id), str(department.id)
    finally:
        db.close()


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


def _seed_publication_versions(app_session, *, site_id: str, year: int, week: int) -> dict[str, object]:
    _seed_site(app_session, site_id=site_id)
    department_id = f"dept-demand-{site_id}"
    tenant_id, site_id, department_id = _seed_department(app_session, site_id=site_id, department_id=department_id)

    with app_session.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.extensions["builder_flow"] = builder_flow

        builder_flow.create_menu(
            menu_id="builder-menu-demand",
            site_id=site_id,
            week_key=f"{year}-W{week:02d}",
            version=1,
            status="published",
        )
        composition_service.create_composition(composition_id="comp-a", composition_name="Soup A")
        composition_service.create_composition(composition_id="comp-b", composition_name="Soup B")
        composition_service.create_composition(
            composition_id="comp-fixed",
            composition_name="Fixed Soup",
            use_custom_menu_name=True,
            menu_name="Fixed Soup",
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-demand",
            menu_detail_id="builder-menu-demand-row-a",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp-a",
            sort_order=10,
            selection_group_id="grp_x",
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-demand",
            menu_detail_id="builder-menu-demand-row-b",
            day="monday",
            meal_slot="lunch_alt2",
            composition_id="comp-b",
            sort_order=20,
            selection_group_id="grp_x",
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-demand",
            menu_detail_id="builder-menu-demand-row-fixed",
            day="tuesday",
            meal_slot="lunch_alt1",
            composition_id="comp-fixed",
            sort_order=30,
            selection_group_id=None,
        )

        legacy_menu_id = MenuServiceDB().create_or_get_menu(tenant_id=tenant_id, site_id=site_id, week=week, year=year).id
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-demand",
            source="manual",
        )

    return {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "department_id": department_id,
        "legacy_menu_id": legacy_menu_id,
        "builder_flow": builder_flow,
        "composition_service": composition_service,
    }


def _publish_versions(app_session, monkeypatch, seed: dict[str, object], *, year: int, week: int) -> None:
    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)
    with app_session.app_context():
        MenuServiceDB().publish_menu(tenant_id=int(seed["tenant_id"]), menu_id=int(seed["legacy_menu_id"]))
        builder_flow = seed["builder_flow"]
        builder_flow.update_composition_menu_row(
            menu_id="builder-menu-demand",
            menu_detail_id="builder-menu-demand-row-a",
            day="tuesday",
            meal_slot="lunch_alt1",
            composition_id="comp-a",
            selection_group_id="grp_y",
            sort_order=10,
        )
        builder_flow._menu_service.update_menu("builder-menu-demand", version=2, status="published")
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=int(seed["tenant_id"]),
            site_id=str(seed["site_id"]),
            year=year,
            week=week,
            builder_menu_id="builder-menu-demand",
            source="manual",
        )
        MenuServiceDB().publish_menu(tenant_id=int(seed["tenant_id"]), menu_id=int(seed["legacy_menu_id"]))


def test_department_menu_row_demand_service_accepts_historical_revision_and_upserts(app_session, monkeypatch):
    site_id = "site-demand-service"
    year = 2026
    week = 16
    seed = _seed_publication_versions(app_session, site_id=site_id, year=year, week=week)
    _publish_versions(app_session, monkeypatch, seed, year=year, week=week)

    service = DepartmentMenuRowDemandService()
    first = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-a",
        selection_group_id="grp_x",
        quantity=14,
    )
    second = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-b",
        selection_group_id="grp_x",
        quantity=4,
    )
    fixed = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=2,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-fixed",
        selection_group_id=None,
        quantity=7,
    )
    historical = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-a",
        selection_group_id="grp_x",
        quantity=12,
    )

    assert first["quantity"] == 14
    assert second["quantity"] == 4
    assert fixed["selection_group_id"] is None
    assert historical["quantity"] == 12

    current = service.get_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-a",
    )
    assert current is not None
    assert current["quantity"] == 12

    same_group_rows = service.list_for_selection_group(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        selection_group_id="grp_x",
    )
    assert len(same_group_rows) == 2

    by_day = service.list_for_department_weekday(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
    )
    assert len(by_day) == 2

    by_row = service.list_for_builder_menu_row_id(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        builder_menu_row_id="builder-menu-demand-row-a",
    )
    assert len(by_row) == 1

    db = get_session()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM department_menu_row_demands")).fetchone()[0]
        scoped_count = db.execute(
            text(
                "SELECT COUNT(*) FROM department_menu_row_demands "
                "WHERE tenant_id=:tenant_id AND site_id=:site_id AND department_id=:department_id"
            ),
            {
                "tenant_id": seed["tenant_id"],
                "site_id": site_id,
                "department_id": seed["department_id"],
            },
        ).fetchone()[0]
        assert int(count) >= 3
        assert int(scoped_count) == 3
    finally:
        db.close()


def test_department_menu_row_demand_service_accepts_fixed_row_null_group(app_session, monkeypatch):
    site_id = "site-demand-fixed"
    year = 2026
    week = 17
    seed = _seed_publication_versions(app_session, site_id=site_id, year=year, week=week)
    _publish_versions(app_session, monkeypatch, seed, year=year, week=week)

    service = DepartmentMenuRowDemandService()
    row = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=2,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-fixed",
        selection_group_id=None,
        quantity=9,
    )

    assert row["selection_group_id"] is None
    assert row["quantity"] == 9


@pytest.mark.parametrize(
    "kwargs, expected_error",
    [
        (
            {
                "builder_menu_id": "missing-menu",
                "builder_menu_version": 1,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 1,
                "selection_group_id": "grp_x",
                "quantity": 1,
            },
            "publication_revision_missing",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 99,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 1,
                "selection_group_id": "grp_x",
                "quantity": 1,
            },
            "publication_revision_missing",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 1,
                "builder_menu_row_id": "does-not-exist",
                "weekday": 1,
                "selection_group_id": "grp_x",
                "quantity": 1,
            },
            "published_row_missing",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 1,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 2,
                "selection_group_id": "grp_x",
                "quantity": 1,
            },
            "weekday_mismatch",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 1,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 1,
                "selection_group_id": "grp_y",
                "quantity": 1,
            },
            "selection_group_mismatch",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 1,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 1,
                "selection_group_id": None,
                "quantity": -1,
            },
            "quantity_invalid",
        ),
        (
            {
                "builder_menu_id": "builder-menu-demand",
                "builder_menu_version": 1,
                "builder_menu_row_id": "builder-menu-demand-row-a",
                "weekday": 1,
                "selection_group_id": "grp_x",
                "quantity": "abc",
            },
            "quantity_invalid",
        ),
    ],
)
def test_department_menu_row_demand_service_rejects_invalid_inputs(app_session, monkeypatch, kwargs, expected_error):
    site_id = "site-demand-invalid"
    year = 2026
    week = 18
    seed = _seed_publication_versions(app_session, site_id=site_id, year=year, week=week)
    _publish_versions(app_session, monkeypatch, seed, year=year, week=week)

    service = DepartmentMenuRowDemandService()
    with pytest.raises(DepartmentMenuRowDemandError) as exc_info:
        service.write_for_row(
            tenant_id=seed["tenant_id"],
            site_id=site_id,
            department_id=seed["department_id"],
            year=year,
            week=week,
            **kwargs,
        )
    assert expected_error in str(exc_info.value)


def test_department_menu_row_demand_service_uses_historical_v1_after_v2_is_active(app_session, monkeypatch):
    site_id = "site-demand-history"
    year = 2026
    week = 19
    seed = _seed_publication_versions(app_session, site_id=site_id, year=year, week=week)
    _publish_versions(app_session, monkeypatch, seed, year=year, week=week)

    service = DepartmentMenuRowDemandService()
    historical = service.write_for_row(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        department_id=seed["department_id"],
        year=year,
        week=week,
        weekday=1,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=1,
        builder_menu_row_id="builder-menu-demand-row-a",
        selection_group_id="grp_x",
        quantity=6,
    )
    current_active = CommunBuilderPublicationService().get_publication_for_week(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        year=year,
        week=week,
    )

    assert historical["quantity"] == 6
    assert current_active is not None
    assert int(current_active.builder_menu_version) == 2
    assert "grp_y" in str(current_active.projection_snapshot_json)
    assert get_shadow_projection_reader().get_projection_for_pinned_menu(
        tenant_id=seed["tenant_id"],
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id="builder-menu-demand",
        builder_menu_version=2,
    ).status == "ok"
