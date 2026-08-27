from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from core.app_factory import create_app
from core.builder import BuilderFlow
from core.db import create_all, get_session
from core.models import CommunBuilderPublicationPin, Site, Tenant
from core.planera_v2.adapters import build_planera_input_from_effective_menu_context
from core.planera_v2.adapters import build_effective_planning_menu_payload
from core.planera_v2.contracts import EffectiveMenuReadiness, EffectiveMenuSourceType
from core.planera_v2.service import build_plan_request_from_adapter_payload
from core.builder.library_scope import ActorContext
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.menu import InMemoryCompositionAliasRepository, MenuService
from modules.offshore2.effective_menu import _service as effective_menu_service
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import OffshoreInstallationSettings, OffshoreWorkMenuDecision
from modules.offshore2.periods import _service as period_service
from modules.offshore2.services import _service as offshore_service


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).filter_by(id=1).first():
                db.add(Tenant(id=1, name="Tenant One"))
            if not db.query(Tenant).filter_by(id=2).first():
                db.add(Tenant(id=2, name="Tenant Two"))
            db.commit()
        finally:
            db.close()
    app.feature_registry.set("offshore.v2.enabled", True)
    return app


def _seed_site(app, *, tenant_id: int, name: str) -> str:
    site_id = str(uuid.uuid4())
    with app.app_context():
        db = get_session()
        try:
            db.add(Site(id=site_id, name=name, tenant_id=tenant_id))
            db.commit()
        finally:
            db.close()
    return site_id


def _seed_installation(app, *, tenant_id: int, site_id: str, visibility_json: str | None = None) -> None:
    with app.app_context():
        db = get_session()
        try:
            db.merge(
                OffshoreInstallationSettings(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    timezone="Europe/Oslo",
                    default_locale="sv",
                    default_theme="system",
                    default_portions=120,
                    menu_track_visibility_json=visibility_json or '{"primary":[{"key":"koett","label":"Kött"},{"key":"fisk","label":"Fisk"}],"secondary":[{"key":"soppa","label":"Soppa"},{"key":"vegetariskt","label":"Vegetariskt"}]}',
                    is_active=True,
                )
            )
            db.commit()
        finally:
            db.close()


def _seed_publication(app, *, tenant_id: int, site_id: str, day: date, builder_menu_id: str, builder_version: int = 4):
    iso = day.isocalendar()
    with app.app_context():
        db = get_session()
        try:
            db.add(
                CommunBuilderPublicationPin(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=int(iso.year),
                    week=int(iso.week),
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_version,
                    source="manual",
                )
            )
            db.commit()
        finally:
            db.close()


def _seed_builder_menu(app, *, menu_id: str = "builder-menu-1") -> None:
    with app.app_context():
        composition_repository = InMemoryCompositionRepository()
        alias_repository = InMemoryCompositionAliasRepository()
        recipe_repository = InMemoryRecipeRepository()
        ingredient_repository = InMemoryRecipeIngredientLineRepository()
        builder_flow = BuilderFlow(
            component_service=ComponentService(repository=InMemoryComponentRepository()),
            composition_service=CompositionService(repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
        )
        flow = BuilderMenuContextFlow(
            menu_service=MenuService(composition_repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            recipe_repository=recipe_repository,
            ingredient_repository=ingredient_repository,
            library_flow=builder_flow,
        )
        app.extensions["builder_menu_context_flow"] = flow
        app.extensions["builder_flow"] = builder_flow
        builder_flow.create_composition(composition_id="demo_offshore_kott", composition_name="Demo Offshore Kött")
        builder_flow.create_composition(composition_id="demo_offshore_fisk", composition_name="Demo Offshore Fisk")
        builder_flow.create_composition(composition_id="demo_offshore_soppa", composition_name="Demo Offshore Soppa")
        builder_flow.create_composition(composition_id="demo_offshore_vegetariskt", composition_name="Demo Offshore Vegetariskt")
        for composition_id, composition_name in [
            ("demo_offshore_kott", "Demo Offshore Kött"),
            ("demo_offshore_fisk", "Demo Offshore Fisk"),
            ("demo_offshore_soppa", "Demo Offshore Soppa"),
            ("demo_offshore_vegetariskt", "Demo Offshore Vegetariskt"),
        ]:
            if builder_flow._composition_repository.get(composition_id) is None:
                builder_flow.create_composition(composition_id, composition_name, library_group="demo-offshore")
            builder_flow.add_component_to_composition(
                composition_id=composition_id,
                component_name=composition_name,
                role="main",
            )
        flow.create_menu(menu_id=menu_id, site_id="demo-site", week_key="demo-week", title="Demo Offshore Builder Menu", version=1, status="draft")
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            for meal_slot in ("lunch", "dinner"):
                for sort_order, composition_id in enumerate(("demo_offshore_kott", "demo_offshore_fisk", "demo_offshore_soppa", "demo_offshore_vegetariskt"), start=1):
                    flow.add_composition_menu_row(menu_id=menu_id, day=day, meal_slot=meal_slot, composition_id=composition_id, sort_order=sort_order)


def _seed_period(app, *, tenant_id: int, site_id: str):
    with app.app_context():
        position = offshore_service.create_work_position(tenant_id=tenant_id, site_id=site_id, actor_user_id=None, payload={"name": "Cook", "position_type": "cook"})
        cycle = offshore_service.create_menu_cycle(tenant_id=tenant_id, site_id=site_id, actor_user_id=None, payload={"name": "Cycle", "description": "Demo", "cycle_length": 4, "is_active": True})
        template = period_service.create_period_template(tenant_id=tenant_id, site_id=site_id, name="Week", duration_days=7, active=True, sort_order=1)
        for day_offset in range(7):
            period_service.add_template_event(tenant_id=tenant_id, site_id=site_id, template_id=template.id, day_offset=str(day_offset), local_time=time(11, 30), service_code="lunch", display_name="Lunch", work_position_id=position.id, default_portions=40, active=True)
            period_service.add_template_event(tenant_id=tenant_id, site_id=site_id, template_id=template.id, day_offset=str(day_offset), local_time=time(17, 30), service_code="dinner", display_name="Dinner", work_position_id=position.id, default_portions=40, active=True)
        generation = period_service.create_work_period_from_template(tenant_id=tenant_id, site_id=site_id, period_template_id=template.id, starts_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC), menu_cycle_id=cycle.id, name="Week")
        period_service.update_work_period(tenant_id=tenant_id, site_id=site_id, period_id=generation.work_period.id, payload={"status": "active"})
        return generation.work_period.id


def test_effective_menu_adapter_resolves_published_override_and_free_text() -> None:
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20), builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)

    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[1].id)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = "cook"
        sess["full_name"] = "Henrik"

    with app.app_context():
        db = get_session()
        try:
            events = period_service.list_service_events(1, site_id, period_id)
            first_event = events[0]
            second_event = events[1]
        finally:
            db.close()

    client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(first_event.id),
            "menu_track_key": "fisk",
            "decision_type": "use_builder_composition",
            "selected_builder_composition_id": "demo_offshore_fisk",
        },
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "X-User-Id": "42"},
    )
    client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(second_event.id),
            "menu_track_key": "soppa",
            "decision_type": "use_free_text",
            "free_text": "Dagens soppa",
        },
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "X-User-Id": "42"},
    )

    with app.app_context():
        actor = ActorContext(tenant_id=1, user_id=42, site_id=site_id, role="cook")
        context = effective_menu_service.build_context(tenant_id=1, site_id=site_id, locale="sv", work_period_id=period_id, actor=actor)

    assert context.work_period is not None
    assert context.work_period.id == period_id
    assert len(context.service_events) == 14
    first_items = {item.track_key: item for item in context.service_events[0].items}
    assert first_items["koett"].source_type == EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM
    assert first_items["koett"].readiness == EffectiveMenuReadiness.STRUCTURED
    assert first_items["koett"].builder_composition_reference is not None
    assert first_items["koett"].builder_composition_reference.composition_id == "demo_offshore_kott"
    assert first_items["koett"].builder_composition_reference.composition_name == "Demo Offshore Kött"
    assert len(first_items["koett"].component_references) == 1
    assert first_items["koett"].component_references[0].component_name == "Demo Offshore Kött"
    assert first_items["fisk"].source_type == EffectiveMenuSourceType.OPERATIONAL_BUILDER_OVERRIDE
    assert first_items["fisk"].builder_composition_reference is not None
    assert first_items["fisk"].builder_composition_reference.composition_id == "demo_offshore_fisk"
    assert len(first_items["fisk"].component_references) == 1
    assert first_items["fisk"].component_references[0].component_name == "Demo Offshore Fisk"
    assert first_items["soppa"].source_type == EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM
    assert first_items["soppa"].published_title is not None

    second_items = {item.track_key: item for item in context.service_events[1].items}
    assert second_items["soppa"].source_type == EffectiveMenuSourceType.OPERATIONAL_FREE_TEXT
    assert second_items["soppa"].readiness == EffectiveMenuReadiness.UNRESOLVED
    assert "free_text_item" in second_items["soppa"].warnings
    assert second_items["soppa"].component_references == ()

    with app.app_context():
        db = get_session()
        try:
            events = period_service.list_service_events(1, site_id, period_id)
            first_event = events[0]
        finally:
            db.close()

    client.post(
        "/offshore/work-menu/decisions/reset",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(first_event.id),
            "menu_track_key": "fisk",
        },
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "X-User-Id": "42"},
    )

    with app.app_context():
        actor = ActorContext(tenant_id=1, user_id=42, site_id=site_id, role="cook")
        reset_context = effective_menu_service.build_context(tenant_id=1, site_id=site_id, locale="sv", work_period_id=period_id, actor=actor)

    reset_first_items = {item.track_key: item for item in reset_context.service_events[0].items}
    assert reset_first_items["fisk"].source_type == EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM
    assert reset_first_items["fisk"].builder_composition_reference is not None
    assert reset_first_items["fisk"].builder_composition_reference.composition_id == "demo_offshore_fisk"
    assert reset_first_items["fisk"].component_references[0].component_name == "Demo Offshore Fisk"

    payload = build_planera_input_from_effective_menu_context(context)
    request = build_plan_request_from_adapter_payload(payload)
    assert request.baseline == 0
    assert request.units == []
    assert request.context["adapter_version"] == "effective-menu-adapter/v1"
    assert request.context["service_events"][0]["items"][0]["stable_item_id"]


def test_effective_menu_adapter_marks_empty_state_when_publication_is_missing() -> None:
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)

    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)
        context = effective_menu_service.build_context(tenant_id=1, site_id=site_id, locale="sv", work_period_id=period_id)

    first_item = context.service_events[0].items[0]
    assert first_item.row_state == "empty"
    assert first_item.published_title is None
    assert first_item.effective_title is None
    assert first_item.builder_composition_reference is None


def test_effective_menu_adapter_rejects_cross_tenant_scope() -> None:
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    other_site_id = _seed_site(app, tenant_id=2, name="Rig B")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_installation(app, tenant_id=2, site_id=other_site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20), builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)

    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

    with app.app_context():
        db = get_session()
        try:
            before = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()

    with app.app_context():
        try:
            effective_menu_service.build_context(tenant_id=1, site_id=other_site_id, locale="sv", work_period_id=period_id)
        except LookupError:
            pass
        else:
            raise AssertionError("expected cross-tenant lookup to fail")

    with app.app_context():
        db = get_session()
        try:
            after = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()

    assert before == after