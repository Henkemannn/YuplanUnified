from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
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
from core.db import get_session
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planning_option_review import PlanningOptionReviewService


@dataclass
class _ReviewApiState:
    site_ids: set[str] = field(default_factory=set)
    requirement_group_ids: set[str] = field(default_factory=set)


_STATE: _ReviewApiState | None = None


def _state() -> _ReviewApiState:
    assert _STATE is not None
    return _STATE


@pytest.fixture(autouse=True)
def _review_api_hygiene(app_session):
    global _STATE
    _STATE = _ReviewApiState()
    extension_snapshot = {
        key: (key in app_session.extensions, app_session.extensions.get(key))
        for key in ("builder_menu_context_flow", "builder_flow")
    }
    try:
        yield
    finally:
        db = get_session()
        try:
            for site_id in sorted(_state().site_ids):
                db.execute(text("DELETE FROM department_menu_choices WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_service_overrides WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_group_requirements WHERE group_id IN (SELECT id FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id))"), {"site_id": site_id})
                db.execute(text("DELETE FROM department_requirement_groups WHERE department_id IN (SELECT id FROM departments WHERE site_id = :site_id)"), {"site_id": site_id})
                db.execute(text("DELETE FROM dietary_types WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM departments WHERE site_id = :site_id"), {"site_id": site_id})
                db.execute(text("DELETE FROM sites WHERE id = :site_id"), {"site_id": site_id})
            db.execute(text("DELETE FROM planning_option_review_decisions"))
            db.execute(text("DELETE FROM planning_option_reviews"))
            db.commit()
        finally:
            db.close()
        for key, (existed, value) in extension_snapshot.items():
            if existed:
                app_session.extensions[key] = value
            else:
                app_session.extensions.pop(key, None)
        _STATE = None


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


def _seed_site(site_id: str, tenant_id: int = 1) -> None:
    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"),
            {"id": site_id, "name": f"Site {site_id}", "tenant_id": tenant_id},
        )
        db.commit()
    finally:
        db.close()
    _state().site_ids.add(site_id)


def _seed_department(site_id: str, name: str, resident_count: int = 10) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return department


def _seed_requirement(site_id: str, name: str, requirement_key: str) -> int:
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


def _seed_publication(app_session, *, site_id: str, year: int, week: int, builder_menu_id: str, day: str) -> dict[str, str]:
    with app_session.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        app_session.extensions["builder_menu_context_flow"] = builder_flow
        app_session.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(
            menu_id=builder_menu_id,
            site_id=site_id,
            week_key=f"{year}-W{week:02d}",
            version=1,
            status="published",
        )
        composition_service.create_composition(composition_id="comp-alt1", composition_name="Fläskkarré")
        composition_service.create_composition(composition_id="comp-alt2", composition_name="Kokt torsk")
        builder_flow.add_composition_menu_row(
            menu_id=builder_menu_id,
            menu_detail_id="detail-1",
            day=day,
            meal_slot="lunch_alt1",
            composition_id="comp-alt1",
            sort_order=10,
        )
        builder_flow.add_composition_menu_row(
            menu_id=builder_menu_id,
            menu_detail_id="detail-2",
            day=day,
            meal_slot="lunch_alt2",
            composition_id="comp-alt2",
            sort_order=20,
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
            projection_snapshot_json=__import__("json").dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        return {str(row.variant_type): str(row.builder_menu_row_id) for row in outcome.projection.rows if str(row.day) == day and str(row.meal) == "lunch"}


def _seed_scenario(app_session, *, include_groups: bool = True, include_unassigned: bool = True) -> tuple:
    service_date = date(2026, 9, 8)
    year, week, _weekday = service_date.isocalendar()
    site_id = f"review-ui-{uuid.uuid4()}"
    _seed_site(site_id)
    dept_a = _seed_department(site_id, "Avdelning A", resident_count=18)
    dept_b = _seed_department(site_id, "Avdelning B", resident_count=12)
    dept_c = _seed_department(site_id, "Avdelning C", resident_count=9) if include_unassigned else None
    group_a = group_b = group_c = None
    if include_groups:
        req_a = _seed_requirement(site_id, f"Glutenfri {uuid.uuid4().hex[:8]}", f"req_gluten_{uuid.uuid4().hex[:8]}")
        req_b = _seed_requirement(site_id, f"Vegetarisk {uuid.uuid4().hex[:8]}", f"req_veg_{uuid.uuid4().hex[:8]}")
        group_a = _seed_group(department_id=dept_a["id"], requirement_ids=[req_a], quantity=3, label="Glutenfri")
        group_b = _seed_group(department_id=dept_b["id"], requirement_ids=[req_b], quantity=4, label="Vegetarisk")
        if dept_c is not None:
            req_c = _seed_requirement(site_id, f"Laktos {uuid.uuid4().hex[:8]}", f"req_lakt_{uuid.uuid4().hex[:8]}")
            group_c = _seed_group(department_id=dept_c["id"], requirement_ids=[req_c], quantity=2, label="Laktos")
    option_ids = _seed_publication(
        app_session,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=f"builder-menu-{uuid.uuid4().hex[:8]}",
        day=service_date.strftime("%A").lower(),
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
        selected_alt="alt2",
    )
    return service_date, site_id, year, week, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids


def _seed_page2_choices(site_id: str, service_date: date, dept_a: dict, dept_b: dict) -> None:
    year, week, weekday = service_date.isocalendar()
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_a["id"], year=year, week=week, weekday=weekday, selected_alt="alt1")
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_b["id"], year=year, week=week, weekday=weekday, selected_alt="alt2")


def _headers(role: str = "admin") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _review_payload(destination_id: str, requirement_group_id: str, decision: str) -> dict[str, str]:
    return {
        "destination_id": destination_id,
        "requirement_group_id": requirement_group_id,
        "decision": decision,
    }


def _review_request(client, site_id: str, service_date: date, option_id: str, decisions: list[dict[str, str]] | None = None):
    return client.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_id,
            "decisions": decisions or [],
        },
        headers=_headers(),
    )


def test_review_write_all_unchecked_saves_explicit_no_decisions(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED"),
    ])
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["review"]["review_state"] == "REVIEWED_NO_DEVIATIONS"
    assert payload["review"]["decision_count"] == 1


def test_review_write_mixed_checkboxes_saves_complete_decision_set(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    MenuChoiceRepo().set_choice(tenant_id=1, site_id=site_id, department_id=dept_b["id"], year=service_date.isocalendar()[0], week=service_date.isocalendar()[1], weekday=service_date.isocalendar()[2], selected_alt="alt1")
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED"),
        _review_payload(dept_b["id"], group_b["id"], "ADAPTATION_REQUIRED"),
    ])
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["review"]["review_state"] == "REVIEWED_WITH_DEVIATIONS"
    assert payload["review"]["decision_count"] == 2


def test_review_write_zero_requirements_accepts_empty_review(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session, include_groups=False)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [])
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["review"]["review_state"] == "REVIEWED_NO_DEVIATIONS"
    assert payload["review"]["decision_count"] == 0


def test_review_write_missing_group_decision_rejected(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED"),
    ])
    assert resp.status_code == 200
    review = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert review.review_state in ("REVIEWED_NO_DEVIATIONS", "REVIEWED_WITH_DEVIATIONS")
    bad = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [])
    assert bad.status_code == 400


def test_review_write_irrelevant_group_rejected(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_c["id"], group_c["id"], "NO_ADAPTATION_REQUIRED"),
    ])
    assert resp.status_code == 400


def test_review_write_wrong_option_group_rejected(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    resp = _review_request(client_admin, site_id, service_date, option_ids["alt2"], [
        _review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED"),
    ])
    assert resp.status_code == 400


def test_review_write_cross_tenant_site_fails_closed(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    db = get_session()
    try:
        db.execute(text("INSERT INTO tenants(id, name, active) VALUES (2, 'Tenant 2', 1)"))
        db.commit()
    finally:
        db.close()
    with client_admin.session_transaction() as sess:
        sess["tenant_id"] = 2
        sess["user_id"] = 1
        sess["role"] = "admin"
    resp = client_admin.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_ids["alt1"],
            "decisions": [_review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED")],
        },
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert resp.status_code in (403, 404)


def test_review_write_cannot_spoof_tenant_or_user_from_request(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    with client_admin.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 7
        sess["role"] = "admin"
    resp = client_admin.post(
        "/ui/kitchen/planering/day/review",
        json={
            "tenant_id": 999,
            "reviewed_by_user_id": 444,
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_ids["alt1"],
            "decisions": [_review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED")],
        },
        headers=_headers(),
    )
    assert resp.status_code == 200
    state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert state.reviewed_by_user_id == 1


def test_review_write_rereview_replaces_prior_decisions(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    first = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED"),
    ])
    assert first.status_code == 200
    second = _review_request(client_admin, site_id, service_date, option_ids["alt1"], [
        _review_payload(dept_a["id"], group_a["id"], "ADAPTATION_REQUIRED"),
    ])
    assert second.status_code == 200
    payload = second.get_json()
    assert payload["review"]["review_state"] == "REVIEWED_WITH_DEVIATIONS"


def test_review_write_current_truth_comes_from_server_context(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, dept_c, group_a, group_b, group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    service = PlanningOptionReviewService()
    service.save_option_review(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
        decisions=[{"destination_id": dept_a["id"], "requirement_group_id": group_a["id"], "decision": "NO_ADAPTATION_REQUIRED"}],
        reviewed_by_user_id=1,
    )
    DepartmentRequirementGroupServiceOverridesRepo().set_override(group_a["id"], service_date, "lunch", 0)
    resp = client_admin.get(
        f"/ui/kitchen/planering/day?ui=product2&site_id={site_id}&date={service_date.isoformat()}&meal=lunch",
        headers=_headers(),
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Underlaget har ändrats – granska igen." in html
