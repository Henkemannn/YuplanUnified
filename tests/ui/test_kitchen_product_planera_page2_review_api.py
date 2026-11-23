from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import gc
from pathlib import Path
import shutil
import tempfile
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.admin_repo import DepartmentsRepo, SitesRepo
from core.builder import BuilderFlow
from core.builder.library_scope import ObjectScope
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
from core.db import get_session, init_engine
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.planning_option_review import PlanningOptionReviewService
from core.csrf import CSRF_SESSION_KEY
from core.models import Base, Tenant, User
from planera_product2_test_support import authenticate_product2_client


@dataclass
class _ReviewApiState:
    site_ids: set[str] = field(default_factory=set)
    requirement_group_ids: set[str] = field(default_factory=set)


_STATE: _ReviewApiState | None = None


@pytest.fixture()
def app_session(request):
    state = request.config._yuplan_test_db_state
    isolated_root = Path(tempfile.mkdtemp(prefix="yuplan-review-api-"))
    isolated_db = isolated_root / "main.db"
    isolated_builder_db = isolated_root / "builder.db"
    original_db_url = f"sqlite:///{state['main_db'].as_posix()}"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "JWT_SECRET": "secret",
            "database_url": f"sqlite:///{isolated_db.as_posix()}",
            "BUILDER_DB_PATH": str(isolated_builder_db),
            "FORCE_DB_REINIT": True,
        }
    )
    db = get_session()
    try:
        engine = db.get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        db.add(Tenant(id=1, name="Review API Test Tenant", active=True))
        db.flush()
        db.execute(
            text(
                "CREATE TABLE kitchen_user_sites "
                "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.commit()
        yield app
    finally:
        db.close()
        from core import db as db_mod

        if db_mod._SessionFactory is not None:
            db_mod._SessionFactory.remove()
        if db_mod._engine is not None:
            db_mod._engine.dispose(close=True)
        db_mod._SessionFactory = None
        db_mod._engine = None
        init_engine(original_db_url, force=True)
        gc.collect()
        shutil.rmtree(isolated_root)


class _ObjectScopeRepository:
    def __init__(self) -> None:
        self.scopes: dict[tuple[str, str], ObjectScope] = {}

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        return self.scopes.get((object_type, object_id))

    def find_private_fork_id(
        self,
        object_type: str,
        source_object_id: str,
        *,
        tenant_id: int,
        owner_user_id: int,
    ) -> str | None:
        return None

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


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


def _build_builder_menu_context_flow() -> tuple[
    BuilderMenuContextFlow,
    CompositionService,
    _ObjectScopeRepository,
]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()
    scope_repository = _ObjectScopeRepository()

    builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=InMemoryComponentAliasRepository(),
        object_scope_repository=scope_repository,
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=MenuService(composition_repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return menu_context_flow, CompositionService(repository=composition_repository), scope_repository


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
        builder_flow, composition_service, scope_repository = _build_builder_menu_context_flow()
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
        for composition_id in ("comp-alt1", "comp-alt2"):
            scope_repository.set_scope(
                "composition",
                composition_id,
                ObjectScope(
                    tenant_id=1,
                    owner_scope="site",
                    owner_site_id=site_id,
                    owner_user_id=None,
                    visibility="site",
                ),
            )
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


def _review_payload(destination_id: str, requirement_group_id: str, decision: str) -> dict[str, str]:
    return {
        "destination_id": destination_id,
        "requirement_group_id": requirement_group_id,
        "decision": decision,
    }


def _review_request(client, site_id: str, service_date: date, option_id: str, decisions: list[dict[str, str]] | None = None):
    authenticate_product2_client(client, tenant_id=1, site_id=site_id, role="admin")
    return client.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_id,
            "decisions": decisions or [],
        },
        headers={},
    )


def _review_csrf_token(client, app_session) -> str:
    previous = {
        "YUPLAN_STRICT_CSRF": app_session.config.get("YUPLAN_STRICT_CSRF"),
        "STRICT_CSRF_IN_TESTS": app_session.config.get("STRICT_CSRF_IN_TESTS"),
    }
    app_session.config.update(
        {
            "YUPLAN_STRICT_CSRF": True,
            "STRICT_CSRF_IN_TESTS": True,
        }
    )
    try:
        client.get("/health")
        with client.session_transaction() as session:
            token = session.get(CSRF_SESSION_KEY)
        assert token
        return str(token)
    finally:
        app_session.config.update(previous)


def _csrf_review_request(
    client,
    app_session,
    site_id: str,
    service_date: date,
    option_id: str,
    *,
    token: str | None,
    strict: bool,
    decisions: list[dict[str, str]] | None = None,
    session_site_id: str | None = None,
    authenticate: bool = True,
):
    if authenticate:
        authenticate_product2_client(client, tenant_id=1, site_id=session_site_id or site_id, role="admin")
    headers = {"X-CSRF-Token": token} if token is not None else {}
    previous = {
        "YUPLAN_STRICT_CSRF": app_session.config.get("YUPLAN_STRICT_CSRF"),
        "STRICT_CSRF_IN_TESTS": app_session.config.get("STRICT_CSRF_IN_TESTS"),
    }
    app_session.config.update(
        {
            "YUPLAN_STRICT_CSRF": strict,
            "STRICT_CSRF_IN_TESTS": True,
        }
    )
    try:
        return client.post(
            "/ui/kitchen/planering/day/review",
            json={
                "site_id": site_id,
                "service_date": service_date.isoformat(),
                "meal": "lunch",
                "option_id": option_id,
                "decisions": decisions or [],
            },
            headers=headers,
        )
    finally:
        app_session.config.update(previous)


@pytest.mark.parametrize("strict", [False, True])
def test_review_write_requires_csrf_in_both_modes(client_admin, app_session, strict):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    token = _review_csrf_token(client_admin, app_session)
    valid = _csrf_review_request(
        client_admin,
        app_session,
        site_id,
        service_date,
        option_ids["alt1"],
        token=token,
        strict=strict,
        decisions=[_review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED")],
    )
    assert valid.status_code == 200
    before = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    denied = _csrf_review_request(
        client_admin,
        app_session,
        site_id,
        service_date,
        option_ids["alt1"],
        token=None,
        strict=strict,
    )
    assert denied.status_code == 403
    after = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert after.review_state == before.review_state
    assert after.decision_count == before.decision_count


def test_review_write_rejects_invalid_csrf_without_changing_review(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    _review_csrf_token(client_admin, app_session)
    denied = _csrf_review_request(
        client_admin,
        app_session,
        site_id,
        service_date,
        option_ids["alt1"],
        token="invalid-token",
        strict=False,
    )
    assert denied.status_code == 403
    state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert state.review_state == "UNREVIEWED"


def test_review_write_with_valid_csrf_rejects_other_site_and_historical_binding(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    other_site = f"review-other-{uuid.uuid4()}"
    _seed_site(other_site)
    authenticate_product2_client(client_admin, tenant_id=1, site_id=site_id, role="admin")
    with client_admin.session_transaction() as session:
        user_id = session["user_id"]
    db = get_session()
    try:
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": user_id, "site_id": other_site},
            )
            db.commit()
        db.rollback()
    finally:
        db.close()
    token = _review_csrf_token(client_admin, app_session)
    denied = _csrf_review_request(
        client_admin,
        app_session,
        other_site,
        service_date,
        option_ids["alt1"],
        token=token,
        strict=False,
        session_site_id=site_id,
        authenticate=False,
    )
    assert denied.status_code == 403
    state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert state.review_state == "UNREVIEWED"


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
    reloaded = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert reloaded.review_is_stale is False
    assert reloaded.review_state == "REVIEWED_WITH_DEVIATIONS"
    assert reloaded.review_basis_hash == reloaded.current_basis_hash


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


def _login_isolated_review_admin(client, site_id: str) -> None:
    email = f"review-cross-tenant-{uuid.uuid4().hex}@example.test"
    password = f"Review-{uuid.uuid4().hex}"
    db = get_session()
    try:
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        max_user_id = int(db.execute(text("SELECT COALESCE(MAX(id), 0) FROM users")).scalar() or 0)
        max_binding_id = int(
            db.execute(text("SELECT COALESCE(MAX(user_id), 0) FROM kitchen_user_sites")).scalar() or 0
        )
        user = User(
            id=max(max_user_id, max_binding_id) + 1,
            tenant_id=1,
            username=email,
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
            auth_version=1,
            is_active=True,
        )
        db.add(user)
        user_id = int(user.id)
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, 1, :site_id)"
            ),
            {"user_id": user_id, "site_id": site_id},
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["user_id"] == user_id
        assert session["tenant_id"] == 1
        assert session["site_id"] == site_id
        assert session["auth_version"] == 1


def test_review_write_cross_tenant_site_fails_closed(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _login_isolated_review_admin(client_admin, site_id)
    db = get_session()
    try:
        foreign_tenant = Tenant(name=f"Review Foreign Tenant {uuid.uuid4().hex}")
        db.add(foreign_tenant)
        db.flush()
        foreign_site, _ = SitesRepo().create_site(
            name=f"Review Foreign Site {uuid.uuid4().hex}",
            tenant_id=int(foreign_tenant.id),
        )
        foreign_site_id = str(foreign_site["id"])
        db.commit()
    finally:
        db.close()
    token = _review_csrf_token(client_admin, app_session)
    before = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    resp = _csrf_review_request(
        client_admin,
        app_session,
        foreign_site_id,
        service_date,
        option_ids["alt1"],
        token=token,
        strict=False,
        decisions=[_review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED")],
        authenticate=False,
    )
    assert resp.status_code == 403
    after = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert after.review_state == before.review_state
    assert after.decision_count == before.decision_count


def test_review_write_historical_binding_cannot_switch_site(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    initial = _review_request(
        client_admin,
        site_id,
        service_date,
        option_ids["alt1"],
        [_review_payload(dept_a["id"], group_a["id"], "NO_ADAPTATION_REQUIRED")],
    )
    assert initial.status_code == 200
    with app_session.app_context():
        other_site, _ = SitesRepo().create_site(name="Historical Other Site", tenant_id=1)
    with client_admin.session_transaction() as sess:
        user_id = sess["user_id"]
        active_site_id = sess["site_id"]
    db = get_session()
    try:
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": user_id, "site_id": other_site["id"]},
            )
            db.commit()
        db.rollback()
    finally:
        db.close()
    denied = client_admin.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": other_site["id"],
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_ids["alt1"],
            "decisions": [],
        },
        headers={},
    )
    assert denied.status_code == 403
    state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=active_site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert state.review_state == "REVIEWED_NO_DEVIATIONS"


def test_review_write_without_active_site_or_binding_is_denied(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, _group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    authenticate_product2_client(client_admin, tenant_id=1, site_id=site_id, role="admin")
    with client_admin.session_transaction() as sess:
        sess.pop("site_id", None)
    no_site = client_admin.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_ids["alt1"],
            "decisions": [],
        },
        headers={},
    )
    assert no_site.status_code in (401, 403)
    authenticate_product2_client(client_admin, tenant_id=1, site_id=site_id, role="admin")
    with client_admin.session_transaction() as sess:
        user_id = sess["user_id"]
    db = get_session()
    try:
        db.execute(
            text("DELETE FROM kitchen_user_sites WHERE user_id = :user_id AND site_id = :site_id"),
            {"user_id": user_id, "site_id": site_id},
        )
        db.commit()
    finally:
        db.close()
    no_binding = client_admin.post(
        "/ui/kitchen/planering/day/review",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "option_id": option_ids["alt1"],
            "decisions": [],
        },
        headers={},
    )
    assert no_binding.status_code in (401, 403)


def test_review_write_cannot_spoof_tenant_or_user_from_request(client_admin, app_session):
    service_date, site_id, _year, _week, dept_a, dept_b, _dept_c, group_a, group_b, _group_c, option_ids = _seed_scenario(app_session)
    _seed_page2_choices(site_id, service_date, dept_a, dept_b)
    authenticate_product2_client(client_admin, tenant_id=1, site_id=site_id, role="admin")
    with client_admin.session_transaction() as sess:
        authenticated_user_id = sess["user_id"]
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
        headers={},
    )
    assert resp.status_code == 200
    state = PlanningOptionReviewService().get_option_review_state(
        tenant_id=1,
        site_id=site_id,
        service_date=service_date,
        meal="lunch",
        option_id=option_ids["alt1"],
    )
    assert state.reviewed_by_user_id == authenticated_user_id


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
    authenticate_product2_client(client_admin, tenant_id=1, site_id=site_id, role="admin")
    resp = client_admin.get(
        f"/ui/kitchen/planering/day?ui=product2&site_id={site_id}&date={service_date.isoformat()}&meal=lunch",
        headers={},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Underlaget har ändrats – granska igen." in html
