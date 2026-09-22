from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
import uuid
from pathlib import Path

import pytest
from flask import current_app
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
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
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planera_product2_page2_context import build_product2_page2_planning_context


HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@dataclass
class _Page2UiState:
    tenant_ids: set[int] = field(default_factory=set)
    site_ids: set[str] = field(default_factory=set)
    requirement_group_ids: set[str] = field(default_factory=set)


_PAGE2_UI_STATE: _Page2UiState | None = None


@pytest.fixture(autouse=True)
def _page2_ui_hygiene(app_session):
    global _PAGE2_UI_STATE
    state = _Page2UiState()
    _PAGE2_UI_STATE = state
    extension_snapshot = {
        key: (key in app_session.extensions, app_session.extensions.get(key))
        for key in ("builder_menu_context_flow", "builder_flow")
    }
    try:
        yield state
    finally:
        db = None
        try:
            from core.db import get_session

            db = get_session()
            for site_id in sorted(state.site_ids):
                db.execute(text("DELETE FROM commun_builder_publication_pins WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_menu_choices WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_service_overrides WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_requirements WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id)"), {"site_id": site_id})
                db.execute(text("DELETE FROM dietary_types WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM departments WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM sites WHERE id = :site_id"), {"site_id": site_id})
            for tenant_id in sorted(state.tenant_ids):
                if int(tenant_id) == 1:
                    continue
                db.execute(text("DELETE FROM tenants WHERE id = :tenant_id"), {"tenant_id": int(tenant_id)})
            for group_id in sorted(state.requirement_group_ids):
                db.execute(text("DELETE FROM department_requirement_group_service_overrides WHERE group_id = :group_id"), {"group_id": group_id})
                db.execute(text("DELETE FROM department_requirement_group_requirements WHERE group_id = :group_id"), {"group_id": group_id})
                db.execute(text("DELETE FROM department_requirement_groups WHERE id = :group_id"), {"group_id": group_id})
            db.commit()
        finally:
            if db is not None:
                db.close()
        for key, (existed, value) in extension_snapshot.items():
            if existed:
                app_session.extensions[key] = value
            else:
                app_session.extensions.pop(key, None)
        _PAGE2_UI_STATE = None


def _state() -> _Page2UiState:
    assert _PAGE2_UI_STATE is not None
    return _PAGE2_UI_STATE


def _headers(role: str = "admin") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


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


def _seed_site(app, *, site_name: str, tenant_id: int = 1) -> str:
    if tenant_id != 1:
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:id, :name, 1)"),
                {"id": tenant_id, "name": f"Tenant {tenant_id}"},
            )
            db.commit()
        finally:
            db.close()
        _state().tenant_ids.add(int(tenant_id))
    site, _ = SitesRepo().create_site(name=site_name, tenant_id=tenant_id)
    _state().site_ids.add(site["id"])
    return site["id"]


def _seed_department(*, site_id: str, name: str, resident_count: int) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_requirement(site_id: str, name: str, requirement_key: str) -> int:
    from core.db import get_session

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
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)
    _state().requirement_group_ids.add(str(group["id"]))
    return group


def _seed_publication(
    app,
    *,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    rows: list[tuple[str, str, str, int]],
) -> dict[str, str]:
    with app.app_context():
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
        for index, (day, meal_slot, composition_name, sort_order) in enumerate(rows, start=1):
            composition_id = f"comp-{builder_menu_id}-{index}"
            composition_service.create_composition(
                composition_id=composition_id,
                composition_name=composition_name,
            )
            builder_flow.add_composition_menu_row(
                menu_id=builder_menu_id,
                menu_detail_id=f"detail-{index}",
                day=day,
                meal_slot=meal_slot,
                composition_id=composition_id,
                sort_order=sort_order,
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
            if str(row.day) == "tuesday" and str(row.meal) == "lunch" and str(row.variant_type)
        }


def _seed_common_page2_data(
    app,
    *,
    site_name: str,
    with_publication: bool = True,
    rows: list[tuple[str, str, str, int]] | None = None,
    include_third_destination: bool = False,
):
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = _seed_site(app, site_name=site_name)
    dept_a = _seed_department(site_id=site_id, name="Avdelning A", resident_count=18)
    dept_b = _seed_department(site_id=site_id, name="Avdelning B", resident_count=12)
    req_a = _seed_requirement(site_id, "Glutenfri", f"req_gluten_{uuid.uuid4().hex[:8]}")
    req_b = _seed_requirement(site_id, "Timbal", f"req_timbal_{uuid.uuid4().hex[:8]}")
    group_a = _seed_group(department_id=dept_a["id"], requirement_ids=[req_a], quantity=9, label="Glutenfri")
    group_b = _seed_group(department_id=dept_b["id"], requirement_ids=[req_b], quantity=8, label="Timbal")
    dept_c = None
    group_c = None
    if include_third_destination:
        dept_c = _seed_department(site_id=site_id, name="Avdelning C", resident_count=16)
        req_c = _seed_requirement(site_id, "Äggfri", f"req_egg_{uuid.uuid4().hex[:8]}")
        group_c = _seed_group(department_id=dept_c["id"], requirement_ids=[req_c], quantity=1, label="Äggfri")
    row_ids = {}
    if with_publication:
        row_ids = _seed_publication(
            app,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
            rows=rows or [
                ("tuesday", "lunch_alt1", "Fläskkarré", 10),
                ("tuesday", "lunch_alt2", "Kokt torsk", 20),
            ],
        )
    return service_date, site_id, dept_a, dept_b, dept_c, group_a, group_b, group_c, row_ids


def _page2_path(site_id: str, service_date: date, meal: str = "lunch", ui: str = "product2") -> str:
    return f"/ui/kitchen/planering/day?ui={ui}&site_id={site_id}&date={service_date.isoformat()}&meal={meal}"


def test_route_requires_kitchen_roles(client_admin, app_session):
    service_date, site_id, *_rest = _seed_common_page2_data(app_session, site_name="Role Site")
    rv = client_admin.get(_page2_path(site_id, service_date), headers=_headers("viewer"))
    assert rv.status_code == 403

    rv_ok = client_admin.get(_page2_path(site_id, service_date), headers=_headers("admin"))
    assert rv_ok.status_code == 200


def test_route_requires_ui_product2(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest = _seed_common_page2_data(app_session, site_name="UI Site")
    rv = client.get(_page2_path(site_id, service_date, ui="legacy"), headers=_headers())
    assert rv.status_code == 404
    rv_missing = client.get(f"/ui/kitchen/planering/day?site_id={site_id}&date={service_date.isoformat()}&meal=lunch", headers=_headers())
    assert rv_missing.status_code == 404


def test_cross_tenant_site_fails_closed(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    site_id = _seed_site(app_session, site_name="Cross Tenant", tenant_id=2)
    rv = client.get(_page2_path(site_id, date(2026, 9, 8)), headers=_headers())
    assert rv.status_code == 404


def test_invalid_date_and_unsupported_meal_fail_closed(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest = _seed_common_page2_data(app_session, site_name="Validation Site")
    bad_date = client.get(f"/ui/kitchen/planering/day?ui=product2&site_id={site_id}&date=not-a-date&meal=lunch", headers=_headers())
    bad_meal = client.get(_page2_path(site_id, service_date, meal="dinner"), headers=_headers())
    assert bad_date.status_code == 404
    assert bad_meal.status_code == 404


def test_two_options_render_titles_and_destination_labels(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, dept_a, dept_b, dept_c, group_a, group_b, group_c, row_ids = _seed_common_page2_data(
        app_session,
        site_name="Two Option Site",
        include_third_destination=True,
    )
    year, week, weekday = service_date.isocalendar()
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=weekday, selected_alt="alt1")
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_b["id"], year=year, week=week, weekday=weekday, selected_alt="alt2")

    context = build_product2_page2_planning_context(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
    )
    option_ids = {option.variant_type: option.option_id for option in context.options}
    destinations = {destination.destination_id: destination for destination in context.destinations}
    groups = {group.destination_id: group for group in context.requirement_groups}
    assert [option.variant_type for option in context.options] == ["alt1", "alt2"]
    assert destinations[dept_a["id"]].selected_option_id == option_ids["alt1"]
    assert destinations[dept_b["id"]].selected_option_id == option_ids["alt2"]
    assert destinations[dept_c["id"]].selected_option_id is None
    assert destinations[dept_c["id"]].choice_source == "none"
    assert groups[dept_a["id"]].label == "Glutenfri"
    assert groups[dept_b["id"]].label == "Timbal"
    assert groups[dept_c["id"]].label == "Äggfri"

    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "PLANERA DAGEN" in html
    assert "Tisdag 8 september" in html
    assert "LUNCH" in html
    assert 'role="tablist"' in html
    assert html.count('data-page2-option-tab') == 2
    assert html.count('data-page2-option-panel') == 2
    assert "2 val" in html
    assert "Alt 1" in html
    assert "Fläskkarré" in html
    assert "Alt 2" in html
    assert "Kokt torsk" in html
    assert "Avdelning A" in html
    assert "Avdelning B" in html
    assert "Avdelning C" in html
    assert "Vilka kan inte äta den här rätten som den är?" in html
    assert "LUNCH · ALT 1" in html
    assert "KOSTBEHOV" in html
    assert "Avdelning A" in html
    assert "Avdelning B" in html
    assert "Glutenfri" in html
    assert "Timbal" in html
    assert "Äggfri" not in html
    assert "1 avdelning saknar menyval" in html
    assert "3 menyval" not in html
    assert "Dagens planering" not in html
    assert "Planeringsunderlag" not in html
    assert "För tilldelade destinationer" not in html
    assert "AVDELNINGAR" not in html
    assert "1 st" not in html
    assert "destination saknar menyval" not in html
    assert "Inga relevanta kostbehov för den här rätten ännu." not in html


def test_three_options_render_collection_shape(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest, row_ids = _seed_common_page2_data(
        app_session,
        site_name="Three Option Site",
        rows=[
            ("tuesday", "lunch_main", "Baguette", 5),
            ("tuesday", "lunch_alt1", "Fläskkarré", 10),
            ("tuesday", "lunch_alt2", "Kokt torsk", 20),
        ],
    )
    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Baguette" in html
    assert "Fläskkarré" in html
    assert "Kokt torsk" in html
    assert html.count('data-page2-option-tab') == 3
    assert html.count('role="tabpanel"') == 3

    assert "3 val" in html

def test_missing_choice_renders_neutral_label(app_session):
    client = app_session.test_client()
    service_date, site_id, *_rest, row_ids = _seed_common_page2_data(
        app_session,
        site_name="Missing Choice Site",
        include_third_destination=True,
    )
    context = build_product2_page2_planning_context(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
    )
    destinations = {destination.destination_id: destination for destination in context.destinations}
    assert all(destination.selected_option_id is None for destination in destinations.values())
    assert all(destination.choice_source == "none" for destination in destinations.values())
    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count("data-page2-option-tab") == 2
    assert html.count("role=\"tabpanel\"") == 2
    assert html.count("yp-planera-page2-unassigned__item") == 3
    assert "Avdelning A" in html
    assert "Avdelning B" in html
    assert "Avdelning C" in html
    assert "3 avdelningar saknar menyval" in html
    assert "KOSTBEHOV" in html
    assert "Planeringsunderlag" not in html
    assert "Dagens planering" not in html
    assert "Tilldelade destinationer" not in html
    assert "För tilldelade destinationer" not in html
    assert "destination saknar menyval" not in html
    assert "AVDELNINGAR" not in html
    assert "1 st" not in html


def test_no_publication_renders_empty_state_and_not_work_area(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest = _seed_common_page2_data(app_session, site_name="No Publication Site", with_publication=False)
    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Ingen publicerad lunchmeny" in html
    assert "PLANERA DAGEN" in html
    assert "role=\"tablist\"" not in html
    assert 'data-page2-option-tab' not in html
    assert 'role="tabpanel"' not in html


def test_no_review_or_checkbox_text_exists(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest, row_ids = _seed_common_page2_data(app_session, site_name="No Review Site", include_third_destination=True)
    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    html = rv.get_data(as_text=True)
    assert "Planerad" not in html
    assert "Ej planerad" not in html
    assert "Fortsätt" not in html
    assert '<input type="checkbox"' not in html
    assert 'type="checkbox"' not in html
    assert "review_state" not in html
    assert "selected_deviations" not in html
    assert "special_diets" not in html
    assert "data-page2-option-tab" in html
    assert "data-page2-option-panel" in html
    assert "Planeringsunderlag" not in html
    assert "Tilldelade destinationer" not in html
    assert "För tilldelade destinationer" not in html
    assert "Dagens planering" not in html
    assert "KOSTBEHOV" in html
    assert "AVDELNINGAR" not in html
    assert "1 st" not in html


def test_page2_uses_meal_scoped_route_identity(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
    service_date, site_id, *_rest, row_ids = _seed_common_page2_data(app_session, site_name="Route Identity Site", include_third_destination=True)
    rv = client.get(_page2_path(site_id, service_date), headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Route Identity Site" in html
    assert "Tisdag 8 september" in html
    assert "LUNCH" in html
    assert 'role="tablist"' in html


def test_template_does_not_use_fixed_alt_fields_and_page1_remains_untouched():
    page2_tpl = Path("templates/ui/kitchen_product_planera_page2.html").read_text(encoding="utf-8")
    page1_tpl = Path("templates/ui/kitchen_product_shell_preview.html").read_text(encoding="utf-8")
    page1_css = Path("static/css/planera_product2_page1.css").read_text(encoding="utf-8")
    page2_css = Path("static/css/planera_product2_page2.css").read_text(encoding="utf-8")

    assert "lunch_alt1" not in page2_tpl
    assert "lunch_alt2" not in page2_tpl
    assert "selected_variant" not in page2_tpl
    assert "kitchen_product_planera_page2.html" not in page1_tpl
    assert "planera_product2_page2.css" not in page1_tpl
    assert "yp-planera-page2" not in page1_css
    assert "yp-planera-page2" in page2_css
