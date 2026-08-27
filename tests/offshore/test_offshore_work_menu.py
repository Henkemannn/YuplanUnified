from __future__ import annotations

import uuid
import re
from datetime import UTC, date, datetime, time

import pytest

from core.app_factory import create_app
from core.builder.library_scope import ActorContext
from core.builder.library_scope import ObjectScope
from core.db import create_all, get_session
from core.models import CommunBuilderPublicationPin, Site, Tenant
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import OffshoreInstallationSettings, OffshoreWorkMenuDecision
from modules.offshore2.periods import _service as period_service
from modules.offshore2.services import _service as offshore_service
from modules.offshore2.work_menu import _service as offshore_work_menu_service
from core.builder_api import _get_builder_flow
from core.builder_menu_context_api import _get_menu_context_flow


TEST_WORK_MENU_DAY = datetime.now(UTC).date()


class _MemoryScopeRepository:
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
        for (stored_object_type, object_id), scope in reversed(list(self.scopes.items())):
            if (
                stored_object_type == object_type
                and scope.tenant_id == tenant_id
                and scope.owner_scope == "user"
                and scope.owner_user_id == owner_user_id
                and scope.visibility == "private"
                and scope.source_object_id == source_object_id
            ):
                return object_id
        return None

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


def _headers(role: str, tenant_id: int = 1, user_id: int = 42):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": str(user_id), "X-User-Name": "Henrik"}


def _login(client, *, tenant_id: int, site_id: str, role: str):
    with client.session_transaction() as sess:
        sess["tenant_id"] = tenant_id
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = role
        sess["full_name"] = "Henrik"


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).filter_by(id=1).first():
                db.add(Tenant(id=1, name="Tenant One"))
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
        flow = _get_builder_flow()
        menu_flow = _get_menu_context_flow()
        seeded_compositions = [
            ("demo_offshore_kott", "Demo Offshore Kött", "demo-offshore"),
            ("demo_offshore_fisk", "Demo Offshore Fisk", "demo-offshore"),
            ("demo_offshore_soppa", "Demo Offshore Soppa", "demo-offshore"),
            ("demo_offshore_vegetariskt", "Demo Offshore Vegetariskt", "demo-offshore"),
            ("real_kott_dish", "Köttbullar med potatis och gräddsås", "kott"),
            ("real_fisk_dish", "Cajuan Kyckling med potet og kålsalat", "fisk"),
            ("real_dessert_dish", "Äppelpaj med vaniljsås", "dessert"),
            ("real_ovrigt_dish", "Grönsakssoppa med bröd", "ovrigt"),
        ]
        for composition_id, composition_name, library_group in seeded_compositions:
            flow.create_standalone_component(composition_name)
            if flow._composition_repository.get(composition_id) is None:
                flow.create_composition(composition_id, composition_name, library_group=library_group)
            flow.add_component_to_composition(
                composition_id=composition_id,
                component_name=composition_name,
                role="main",
            )
        menu_flow.create_menu(menu_id=menu_id, site_id="demo-site", week_key="demo-week", title="Demo Offshore Builder Menu", version=1, status="draft")
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            for meal_slot in ("lunch", "dinner"):
                for sort_order, composition_id in enumerate(("demo_offshore_kott", "demo_offshore_fisk", "demo_offshore_soppa", "demo_offshore_vegetariskt", "real_kott_dish", "real_fisk_dish", "real_dessert_dish", "real_ovrigt_dish"), start=1):
                    menu_flow.add_composition_menu_row(menu_id=menu_id, day=day, meal_slot=meal_slot, composition_id=composition_id, sort_order=sort_order)


def _seed_period(app, *, tenant_id: int, site_id: str):
    with app.app_context():
        position = offshore_service.create_work_position(tenant_id=tenant_id, site_id=site_id, actor_user_id=None, payload={"name": "Cook", "position_type": "cook"})
        cycle = offshore_service.create_menu_cycle(tenant_id=tenant_id, site_id=site_id, actor_user_id=None, payload={"name": "Cycle", "description": "Demo", "cycle_length": 4, "is_active": True})
        template = period_service.create_period_template(tenant_id=tenant_id, site_id=site_id, name="Week", duration_days=7, active=True, sort_order=1)
        for day_offset in range(7):
            period_service.add_template_event(tenant_id=tenant_id, site_id=site_id, template_id=template.id, day_offset=str(day_offset), local_time=time(11, 30), service_code="lunch", display_name="Lunch", work_position_id=position.id, default_portions=40, active=True)
            period_service.add_template_event(tenant_id=tenant_id, site_id=site_id, template_id=template.id, day_offset=str(day_offset), local_time=time(17, 30), service_code="dinner", display_name="Dinner", work_position_id=position.id, default_portions=40, active=True)
        generation = period_service.create_work_period_from_template(tenant_id=tenant_id, site_id=site_id, period_template_id=template.id, starts_at=datetime.combine(TEST_WORK_MENU_DAY, time(8, 0), tzinfo=UTC), menu_cycle_id=cycle.id, name="Week")
        period_service.update_work_period(tenant_id=tenant_id, site_id=site_id, period_id=generation.work_period.id, payload={"status": "active"})
        return generation.work_period.id


def _find_track(vm, track_key: str):
    for day in vm.get("days") or ():
        for meal in day.meals:
            for track in meal.tracks:
                if track.track_key == track_key:
                    return track
    return None


def test_offshore_work_menu_renders_tracks_and_saves_decision():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")
    response = client.get("/offshore/work-menu", headers=_headers("cook"))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Arbetsmeny" in html
    assert "Visa på korten" in html
    assert "Kött" in html
    assert "Fisk" in html
    assert "Soppa" in html
    assert "Vegetariskt" in html
    assert "data-work-menu-root" in html
    assert "offshore-work-menu-day-row" in html
    assert "offshore-work-menu-day-marker" in html
    assert "data-work-menu-meal-open" in html
    assert "data-work-menu-track-toggle" in html
    assert "data-work-menu-expand-toggle" in html
    assert "offshoreWorkMenuModal" in html
    assert "data-work-menu-builder-bridge" in html
    assert "data-work-menu-legacy-summary" in html
    assert re.search(r"data-work-menu-legacy-summary[^>]*hidden", html)
    assert "data-work-menu-track-edit" in html
    assert "Ändra rätt" in html
    assert "offshore-work-menu-meal__status" not in html
    assert "offshore-work-menu-meal__meta" not in html

    assert "data-work-menu-builder-open" in html
    assert "data-work-menu-dish-picker" in html
    assert "data-work-menu-picker-browse" in html
    assert "data-work-menu-picker-instruction" in html
    assert "Välj en befintlig rätt eller skapa en ny." in html
    assert html.count('offshore-work-menu-modal__title') == 1
    assert "data-work-menu-picker-search" in html
    assert "data-work-menu-picker-categories" in html
    assert "data-work-menu-picker-relevant" in html
    assert "data-work-menu-picker-results-section" in html
    assert re.search(r"data-work-menu-picker-results-section[^>]*hidden", html)
    assert "data-dish-picker-create-new" in html
    assert "Återställ till" in html
    assert "data-work-menu-composition-options" in html
    assert "data-work-menu-builder-host" in html
    assert "offshore-work-menu-builder-host__backdrop" in html
    assert "offshore-work-menu-builder-host__frame" in html
    assert 'src="/builder-editor-host"' in html
    assert 'src="about:blank"' not in html
    assert 'target="_blank"' not in html
    assert 'data-public-title="' in html
    assert html.count('class="app-shell__card offshore-work-menu-controls"') == 1
    assert html.count('class="offshore-work-menu-controls__header"') == 1
    assert html.count('class="offshore-work-menu-track-filter" data-work-menu-track-filter') == 1
    assert html.count('class="offshore-work-menu-builder-host__panel"') == 1

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook")):
        vm = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )

    options_by_value = {option["value"]: option for option in (vm.get("composition_options") or ())}
    assert options_by_value["real_kott_dish"]["library_group"] == "kott"
    assert options_by_value["real_fisk_dish"]["library_group"] == "fisk"
    assert options_by_value["real_dessert_dish"]["library_group"] == "dessert"
    assert options_by_value["real_ovrigt_dish"]["library_group"] == "ovrigt"
    assert options_by_value["demo_offshore_kott"]["library_group"] == "demo-offshore"
    assert options_by_value["demo_offshore_fisk"]["library_group"] == "demo-offshore"
    assert {option["library_group"] for option in options_by_value.values()} >= {"kott", "fisk", "dessert", "ovrigt", "demo-offshore"}

    with app.app_context():
        flow = _get_builder_flow()
        builder_actor = ActorContext(tenant_id=1, user_id=20, site_id=site_id, role="cook")
        before_count = len(flow.list_library_compositions(actor=builder_actor))
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook")):
        _ = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.app_context():
        flow = _get_builder_flow()
        builder_actor = ActorContext(tenant_id=1, user_id=20, site_id=site_id, role="cook")
        after_count = len(flow.list_library_compositions(actor=builder_actor))
    assert after_count == before_count

    first_day = (vm.get("days") or [])[0]
    first_meal = (first_day.meals or [])[0]
    first_track = next((track for track in (first_meal.tracks or ()) if track.builder_bridge is not None), None)
    assert first_track.builder_bridge is not None
    assert first_track.builder_bridge["composition_name"] == "Demo Offshore Kött"
    assert first_track.builder_bridge["component_count"] == 1
    assert [item["component_name"] for item in first_track.builder_bridge["components"]] == ["Demo Offshore Kött"]
    assert first_track.builder_bridge["builder_url"].startswith("/builder-editor-host?composition_id=")

    js_path = "static/offshore2/work_menu.js"
    with open(js_path, encoding="utf-8") as f:
        js_source = f.read()
    assert "const trackCards = Array.from(root.querySelectorAll('[data-work-menu-track-row]'));" in js_source
    assert "const editButtons = Array.from(root.querySelectorAll('[data-work-menu-track-edit]'));" in js_source
    assert "const picker = root.querySelector('[data-work-menu-dish-picker]');" in js_source
    assert "function openDishPicker(trackButton)" in js_source
    assert "function renderPickerCategories()" in js_source
    assert "function renderPickerResults()" in js_source
    assert "function formatPickerGroupLabel(value)" in js_source
    assert "meta.textContent = formatPickerGroupLabel(item.library_group);" in js_source
    assert "meta.textContent = [groupLabel, item.value]" not in js_source
    assert "setPickerViewMode('confirm');" in js_source
    assert "pickerConfirmSelected.textContent = `→ ${selected.label || 'Vald rätt'}`;" in js_source
    assert "pickerConfirmMeta.textContent = [pickerActiveTrack ? pickerActiveTrack.dataset.dayLabel" in js_source
    assert "pickerResetTitle.textContent = pickerActiveTrack.dataset.publicTitle || pickerActiveTrack.dataset.effectiveTitle || '';" in js_source
    assert "pickerBrowse.hidden = !browsing;" in js_source
    assert "pickerInstruction.hidden = !browsing;" in js_source
    assert "pickerResultsSection.hidden = pickerViewMode === 'confirm' || defaultBrowse;" in js_source
    assert "pickerConfirm.hidden = browsing;" in js_source
    assert "const defaultBrowse = !searchActive && !categoryActive;" in js_source
    assert "setPickerResults(defaultBrowse ? [] : filteredItems, pickerResults, 'Inga rätter matchar sökningen.');" in js_source
    assert "pickerResultsSection.hidden = pickerViewMode === 'confirm' || defaultBrowse;" in js_source
    assert "pickerCategories.addEventListener('click'" in js_source
    assert "pickerResults.addEventListener('click'" in js_source
    assert "pickerSubmit.addEventListener('click'" in js_source
    assert "pickerBack.addEventListener('click'" in js_source
    assert "pickerSubmit.textContent = 'Byter…';" in js_source
    assert "pickerSubmit.disabled = true;" in js_source
    assert "modal.hidden = true;" in js_source
    assert "document.body.classList.remove('offshore-work-menu-modal-open');" in js_source
    assert "window.requestAnimationFrame(() => {" in js_source
    assert "function openModalFromTrack(trackButton, mode = 'default')" in js_source
    assert "modal.dataset.workMenuMode = mode;" in js_source
    assert "function openBuilderHostForCreate(trackButton)" in js_source
    assert "builder-host-create-composition" in js_source
    assert "builder-host-created-composition-ready" in js_source
    assert "pendingBuilderHostCreate = null;" in js_source
    assert "if (payload.type === 'builder-host-created-composition-ready') {" in js_source
    assert "if (lastBuilderHostKind === 'create-composition') {" in js_source
    assert "setPickerViewMode('confirm');" in js_source
    assert "function ensureBuilderFieldOption(option) {" in js_source
    assert "fieldOption.selected = true;" in js_source
    assert "ensureBuilderFieldOption(option);" in js_source
    assert "function buildBuilderBridgeFromComposition(composition, fallbackBridge = null) {" in js_source
    assert "function applyBuilderCompositionPresentation(composition, fallbackBridge = null) {" in js_source
    assert "async function refreshBuilderCompositionPresentation(compositionId, fallbackBridge = null) {" in js_source
    assert "fetch(`/api/builder/compositions/${encodeURIComponent(idValue)}`" in js_source
    assert "row.dataset.builderBridge = serializedBridge;" in js_source
    assert "title.textContent = refreshedBridge.composition_name || compositionId;" in js_source
    assert "const shouldAutoApplyCreateComposition = lastBuilderHostKind === 'create-composition' && Boolean(pickerSelectedOption) && Boolean(saveForm);" in js_source
    assert "const shouldRefreshExistingComposition = lastBuilderHostKind === 'composition' && Boolean(lastBuilderBridge && lastBuilderBridge.composition_id);" in js_source
    assert "if (shouldAutoApplyCreateComposition && saveForm && !pickerSubmitting) {" in js_source
    assert "void refreshBuilderCompositionPresentation(lastBuilderBridge.composition_id, lastBuilderBridge);" in js_source
    assert "closeBuilderHost();" in js_source
    assert "openModalFromTrack(button, 'chooser');" in js_source
    assert "decisionTypeField.value = 'use_builder_composition';" in js_source
    assert "syncModalSections(mode);" in js_source
    assert "if (openBuilderHostFromTrack(row)) {" in js_source
    assert "event.preventDefault();" in js_source
    assert "event.stopPropagation();" in js_source
    assert "openBuilderHostFromTrack(trackButton)" in js_source
    assert "return openBuilderHost(bridge);" in js_source
    assert "return false;" in js_source
    assert "builderHostFrame.src = bridge.builder_url;" not in js_source
    assert "builderHostFrame.src = 'about:blank';" not in js_source
    assert "builderHostRuntimeReady" in js_source
    assert "pendingBuilderHostOpen" in js_source
    assert "postBuilderHostPing()" in js_source
    assert "postBuilderHostOpen(" in js_source
    assert "builder-host-runtime-ready" in js_source
    assert "builder-host-open" in js_source
    assert "window.addEventListener('message'" in js_source
    assert "lastBuilderHostKind" in js_source
    assert "if (lastBuilderHostKind === 'create-composition') {" in js_source
    assert "String(detail.host_target_id || '') !== 'create-composition'" in js_source
    assert "String(detail.host_target_id || '') !== String(lastBuilderBridge.composition_id || '')" in js_source
    assert "String(detail.kind || '') !== lastBuilderHostKind" in js_source
    assert "builder-host-ready" in js_source
    assert "offshore-work-menu-builder-host--ready" in js_source
    assert "offshore-work-menu-builder-host--open" in js_source
    assert "window.scrollTo(lastBuilderHostScrollX, lastBuilderHostScrollY);" in js_source
    assert "pickerResetTitle.textContent = pickerActiveTrack.dataset.publicTitle || pickerActiveTrack.dataset.effectiveTitle || '';" in js_source
    assert "pickerConfirmCurrent.textContent = `Nuvarande rätt: ${pickerActiveTrack ? (pickerActiveTrack.dataset.effectiveTitle || pickerActiveTrack.dataset.publicTitle || '—') : '—'}`;" in js_source

    css_path = "static/offshore2/offshore.css"
    with open(css_path, encoding="utf-8") as f:
        css_source = f.read()
    assert "background: transparent;" in css_source
    assert "appearance: none;" in css_source
    assert "cursor: pointer;" in css_source
    assert "[data-work-menu-picker-confirm][hidden]" in css_source
    assert "[data-work-menu-picker-browse][hidden]" in css_source
    assert "[data-work-menu-picker-results-section][hidden]" in css_source
    assert "[data-work-menu-legacy-summary][hidden]" in css_source

    with app.app_context():
        db = get_session()
        try:
            before = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()

    post = client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
            "decision_type": "use_free_text",
            "free_text": "Today\'s fish",
        },
        headers=_headers("cook"),
        follow_redirects=False,
    )
    assert post.status_code == 302
    assert post.headers["Location"].endswith("/offshore/work-menu")
    with client.session_transaction() as session:
        assert not session.get("_flashes")

    with app.app_context():
        db = get_session()
        try:
            after = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()
    assert after == before + 1

    page_after_save = client.get("/offshore/work-menu", headers=_headers("cook"))
    html_after_save = page_after_save.get_data(as_text=True)
    assert "offshore-work-menu-track-row__indicator" in html_after_save
    assert "Personligt val" in html_after_save
    assert "offshore-work-menu-track-row__badge" not in html_after_save


def test_offshore_work_menu_uses_actor_private_builder_fork_without_creating_new_forks():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

        flow = _get_builder_flow()
        scope_repo = _MemoryScopeRepository()
        flow._object_scope_repository = scope_repo  # type: ignore[attr-defined]
        shared = flow.get_library_composition("demo_offshore_kott", actor=None)
        assert shared is not None
        cook_a_actor = ActorContext(tenant_id=1, user_id=20, site_id=site_id, role="cook")
        cook_b_actor = ActorContext(tenant_id=1, user_id=30, site_id=site_id, role="cook")
        cook_b_private_actor = ActorContext(tenant_id=1, user_id=31, site_id=site_id, role="cook")
        no_fork_actor = ActorContext(tenant_id=1, user_id=40, site_id=site_id, role="cook")
        private_target = flow.resolve_composition_edit_target(shared.composition_id, actor=cook_a_actor)
        private_target = flow.update_composition_metadata(
            private_target.composition_id,
            composition_name="Demo Offshore Kött Cook A",
            actor=cook_a_actor,
        )
        cook_b_private = flow.resolve_composition_edit_target(shared.composition_id, actor=cook_b_private_actor)
        cook_b_private = flow.update_composition_metadata(
            cook_b_private.composition_id,
            composition_name="Demo Offshore K÷tt Cook B",
            actor=cook_b_private_actor,
        )
        composition_count_before = len(flow._composition_service.list_compositions())

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")

    response_a = client.get("/offshore/work-menu")
    assert response_a.status_code == 200

    response_b = client.get("/offshore/work-menu", headers=_headers("cook", user_id=30))
    html_b = response_b.get_data(as_text=True)
    assert response_b.status_code == 200
    assert "Demo Offshore Kött" in html_b

    response_c = client.get("/offshore/work-menu", headers=_headers("cook", user_id=40))
    html_c = response_c.get_data(as_text=True)
    assert response_c.status_code == 200
    assert "Demo Offshore Kött" in html_c

    with app.app_context():
        flow = _get_builder_flow()
        resolved_private = flow.resolve_composition_read_target(shared.composition_id, actor=cook_a_actor)
        resolved_shared = flow.resolve_composition_read_target(shared.composition_id, actor=cook_b_actor)
        resolved_no_fork = flow.resolve_composition_read_target(shared.composition_id, actor=no_fork_actor)

        assert resolved_private is not None
        assert resolved_private.composition_id == private_target.composition_id
        assert resolved_private.composition_name == "Demo Offshore Kött Cook A"
        assert resolved_shared is not None
        assert resolved_shared.composition_id == shared.composition_id
        assert resolved_shared.composition_name == "Demo Offshore Kött"
        assert resolved_no_fork is not None
        assert resolved_no_fork.composition_id == shared.composition_id
        assert len(flow._composition_service.list_compositions()) == composition_count_before

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_a = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    assert any(track.effective_title == "Demo Offshore Kött Cook A" for day in (vm_a.get("days") or ()) for meal in day.meals for track in meal.tracks)

    option_values_a = {option["value"] for option in (vm_a.get("composition_options") or ())}
    assert shared.composition_id in option_values_a
    assert private_target.composition_id in option_values_a
    assert cook_b_private.composition_id not in option_values_a

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=30)):
        vm_b = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=30,
        )
    assert any(track.effective_title == "Demo Offshore Kött" for day in (vm_b.get("days") or ()) for meal in day.meals for track in meal.tracks)

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=40)):
        vm_c = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=40,
        )
    assert any(track.effective_title == "Demo Offshore Kött" for day in (vm_c.get("days") or ()) for meal in day.meals for track in meal.tracks)

    option_values_c = {option["value"] for option in (vm_c.get("composition_options") or ())}
    assert shared.composition_id in option_values_c
    assert private_target.composition_id not in option_values_c
    assert cook_b_private.composition_id not in option_values_c


def test_offshore_work_menu_selected_builder_override_uses_selected_identity_and_components():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)
        flow = _get_builder_flow()

        decision = offshore_work_menu_service.save_decision(
            tenant_id=1,
            site_id=site_id,
            work_period_id=period_id,
            service_event_id=events[0].id,
            menu_track_key="koett",
            decision_type="use_builder_composition",
            selected_builder_composition_id="demo_offshore_fisk",
            free_text=None,
            actor_user_id=20,
        )
        assert decision.selected_builder_composition_id == "demo_offshore_fisk"

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )

    selected_track = None
    for day in vm.get("days") or ():
        for meal in day.meals:
            for track in meal.tracks:
                if track.track_key == "koett":
                    selected_track = track
                    break
            if selected_track is not None:
                break
        if selected_track is not None:
            break

    assert selected_track is not None
    assert selected_track.effective_title == "Demo Offshore Fisk"
    assert selected_track.builder_composition_id == "demo_offshore_fisk"
    assert selected_track.builder_bridge is not None
    assert selected_track.builder_bridge["composition_id"] == "demo_offshore_fisk"
    assert selected_track.builder_bridge["composition_name"] == "Demo Offshore Fisk"
    assert [component["component_id"] for component in selected_track.builder_bridge["components"]] == ["demo_offshore_fisk"]


def test_offshore_work_menu_chooser_submits_real_builder_composition_and_is_personal():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

        flow = _get_builder_flow()
        scope_repo = _MemoryScopeRepository()
        flow._object_scope_repository = scope_repo  # type: ignore[attr-defined]
        shared = flow.get_library_composition("demo_offshore_kott", actor=None)
        assert shared is not None
        cook_a_actor = ActorContext(tenant_id=1, user_id=20, site_id=site_id, role="cook")
        cook_b_actor = ActorContext(tenant_id=1, user_id=30, site_id=site_id, role="cook")
        cook_a_private = flow.resolve_composition_edit_target(shared.composition_id, actor=cook_a_actor)
        cook_a_private = flow.update_composition_metadata(
            cook_a_private.composition_id,
            composition_name="Demo Offshore Kött Cook A",
            actor=cook_a_actor,
        )

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")

    response = client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
            "decision_type": "use_builder_composition",
            "selected_builder_composition_id": cook_a_private.composition_id,
        },
        headers=_headers("cook", user_id=20),
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_a = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=30)):
        vm_b = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=30,
        )

    track_a = _find_track(vm_a, "fisk")
    track_b = _find_track(vm_b, "fisk")
    assert track_a is not None
    assert track_b is not None
    assert track_a.effective_title == "Demo Offshore Kött Cook A"
    assert track_a.builder_composition_id == cook_a_private.composition_id
    assert track_a.builder_bridge is not None
    assert track_a.builder_bridge["composition_id"] == cook_a_private.composition_id
    assert track_a.builder_bridge["composition_name"] == "Demo Offshore Kött Cook A"
    assert track_b.effective_title == "Demo Offshore Fisk"

    with app.app_context():
        db = get_session()
        try:
            rows = db.query(OffshoreWorkMenuDecision).filter_by(tenant_id=1, site_id=site_id, service_event_id=events[0].id, menu_track_key="fisk").all()
        finally:
            db.close()

    assert {(row.owner_user_id, row.selected_builder_composition_id) for row in rows} == {(20, cook_a_private.composition_id)}

    reset_response = client.post(
        "/offshore/work-menu/decisions/reset",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
        },
        headers=_headers("cook", user_id=20),
        follow_redirects=False,
    )
    assert reset_response.status_code == 302
    assert reset_response.headers["Location"].endswith("/offshore/work-menu")
    with client.session_transaction() as session:
        assert not session.get("_flashes")

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_a_reset = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=30)):
        vm_b_reset = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=30,
        )

    track_a_reset = _find_track(vm_a_reset, "fisk")
    track_b_reset = _find_track(vm_b_reset, "fisk")
    assert track_a_reset is not None
    assert track_b_reset is not None
    assert track_a_reset.effective_title == track_a_reset.published_title
    assert track_b_reset.effective_title == "Demo Offshore Fisk"


def test_offshore_work_menu_decisions_are_owner_scoped_and_reset_is_personal():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

        with pytest.raises(ValueError):
            offshore_work_menu_service.save_decision(
                tenant_id=1,
                site_id=site_id,
                work_period_id=period_id,
                service_event_id=events[0].id,
                menu_track_key="fisk",
                decision_type="use_free_text",
                selected_builder_composition_id=None,
                free_text="missing actor",
                actor_user_id=None,
            )
        with pytest.raises(ValueError):
            offshore_work_menu_service.reset_decision(
                tenant_id=1,
                site_id=site_id,
                work_period_id=period_id,
                service_event_id=events[0].id,
                menu_track_key="fisk",
                actor_user_id=None,
            )

        decision_a = offshore_work_menu_service.save_decision(
            tenant_id=1,
            site_id=site_id,
            work_period_id=period_id,
            service_event_id=events[0].id,
            menu_track_key="fisk",
            decision_type="use_free_text",
            selected_builder_composition_id=None,
            free_text="Cook A",
            actor_user_id=20,
        )
        decision_b = offshore_work_menu_service.save_decision(
            tenant_id=1,
            site_id=site_id,
            work_period_id=period_id,
            service_event_id=events[0].id,
            menu_track_key="fisk",
            decision_type="use_free_text",
            selected_builder_composition_id=None,
            free_text="Cook B",
            actor_user_id=30,
        )
        decision_a_updated = offshore_work_menu_service.save_decision(
            tenant_id=1,
            site_id=site_id,
            work_period_id=period_id,
            service_event_id=events[0].id,
            menu_track_key="fisk",
            decision_type="use_free_text",
            selected_builder_composition_id=None,
            free_text="Cook A updated",
            actor_user_id=20,
        )
        legacy_null_owner = OffshoreWorkMenuDecision(
            tenant_id=1,
            site_id=site_id,
            service_event_id=events[0].id,
            menu_track_key="soppa",
            decision_type="use_free_text",
            free_text="Legacy null owner",
            owner_user_id=None,
            source_publication_pin_id=decision_a.source_publication_pin_id,
            source_publication_year=decision_a.source_publication_year,
            source_publication_week=decision_a.source_publication_week,
            created_by_user_id=None,
            updated_by_user_id=None,
        )
        db = get_session()
        try:
            db.add(legacy_null_owner)
            db.commit()
        finally:
            db.close()

    assert decision_a.owner_user_id == 20
    assert decision_a.created_by_user_id == 20
    assert decision_a.updated_by_user_id == 20
    assert decision_b.owner_user_id == 30
    assert decision_b.created_by_user_id == 30
    assert decision_b.updated_by_user_id == 30
    assert decision_a_updated.owner_user_id == 20
    assert decision_a_updated.created_by_user_id == 20
    assert decision_a_updated.updated_by_user_id == 20
    assert decision_a_updated.free_text == "Cook A updated"

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_a = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=30)):
        vm_b = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=30,
        )

    track_a = _find_track(vm_a, "fisk")
    track_b = _find_track(vm_b, "fisk")
    assert track_a is not None
    assert track_b is not None
    assert track_a.effective_title == "Cook A updated"
    assert track_b.effective_title == "Cook B"

    reset_result = offshore_work_menu_service.reset_decision(
        tenant_id=1,
        site_id=site_id,
        work_period_id=period_id,
        service_event_id=events[0].id,
        menu_track_key="fisk",
        actor_user_id=20,
    )
    assert reset_result is True

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_a_after_reset = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=30)):
        vm_b_after_reset = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=30,
        )

    track_a_after_reset = _find_track(vm_a_after_reset, "fisk")
    track_b_after_reset = _find_track(vm_b_after_reset, "fisk")
    assert track_a_after_reset is not None
    assert track_b_after_reset is not None
    assert track_a_after_reset.effective_title == track_a_after_reset.published_title
    assert track_b_after_reset.effective_title == "Cook B"

    with app.app_context():
        db = get_session()
        try:
            rows = db.query(OffshoreWorkMenuDecision).filter_by(tenant_id=1, site_id=site_id, service_event_id=events[0].id, menu_track_key="fisk").all()
            owners = {(row.owner_user_id, row.free_text) for row in rows}
        finally:
            db.close()

    assert (30, "Cook B") in owners
    assert all(owner_user_id != 20 for owner_user_id, _ in owners)


def test_offshore_work_menu_legacy_null_owner_decision_is_anonymous_to_authenticated_cooks():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)
        db = get_session()
        try:
            db.add(
                OffshoreWorkMenuDecision(
                    tenant_id=1,
                    site_id=site_id,
                    service_event_id=events[0].id,
                    menu_track_key="soppa",
                    decision_type="use_free_text",
                    free_text="Legacy null owner",
                    owner_user_id=None,
                    source_publication_pin_id=None,
                    source_publication_year=2026,
                    source_publication_week=34,
                    created_by_user_id=None,
                    updated_by_user_id=None,
                )
            )
            db.commit()
        finally:
            db.close()

    with app.test_request_context("/offshore/work-menu", headers=_headers("cook", user_id=20)):
        vm_actor = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=20,
        )
    with app.test_request_context("/offshore/work-menu", headers=_headers("cook")):
        vm_anonymous = offshore_work_menu_service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            locale="sv",
            theme="system",
            role="cook",
            tenant_name="Tenant One",
            site_name="Rig A",
            actor_user_id=None,
        )

    actor_track = _find_track(vm_actor, "soppa")
    anonymous_track = _find_track(vm_anonymous, "soppa")
    assert actor_track is not None
    assert anonymous_track is not None
    assert actor_track.effective_title == actor_track.published_title
    assert anonymous_track.effective_title == "Legacy null owner"


def test_offshore_work_menu_reset_deletes_decision():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")
    client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
            "decision_type": "use_free_text",
            "free_text": "Today\'s fish",
        },
        headers=_headers("cook"),
        follow_redirects=True,
    )

    with app.app_context():
        db = get_session()
        try:
            before = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()

    response = client.post(
        "/offshore/work-menu/decisions/reset",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
        },
        headers=_headers("cook"),
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        db = get_session()
        try:
            after = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()
    assert after == before - 1




def test_offshore_work_menu_preserves_unknown_track_groups():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(
        app,
        tenant_id=1,
        site_id=site_id,
        visibility_json='{"primary":[{"key":"koett","label":"Kött"}],"secondary":[{"key":"soppa","label":"Soppa"}],"late-night":[{"key":"night","label":"Late night"}]}',
    )
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    _seed_period(app, tenant_id=1, site_id=site_id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    response = client.get("/offshore/work-menu", headers=_headers("viewer"))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Late night" in html
    assert "data-work-menu-track-toggle" in html


def test_offshore_work_menu_hides_editor_controls_for_read_only_role():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    _seed_period(app, tenant_id=1, site_id=site_id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    response = client.get("/offshore/work-menu", headers=_headers("viewer"))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-work-menu-save-form" not in html
    assert "data-work-menu-decision-type" not in html
    assert "data-work-menu-track-edit" not in html
    assert "Ändra rätt" not in html


def test_offshore_work_menu_builder_host_markup_is_chrome_free():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    _seed_period(app, tenant_id=1, site_id=site_id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")
    response = client.get("/offshore/work-menu", headers=_headers("cook"))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'class="offshore-work-menu-builder-host"' in html
    assert 'offshore-work-menu-builder-host__panel' in html
    assert 'offshore-work-menu-builder-host__backdrop' in html
    assert 'offshore-work-menu-builder-host__frame' in html
    assert html.count('class="offshore-work-menu-builder-host"') == 1


def test_offshore_work_menu_rejects_ambiguous_builder_decision():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")
    response = client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
            "decision_type": "use_builder_composition",
            "selected_builder_composition_id": "demo_offshore_fisk",
            "free_text": "Ambiguous",
        },
        headers=_headers("cook"),
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert response.headers.get("Location", "").endswith("/offshore/settings")


def test_offshore_work_menu_rejects_unknown_builder_composition():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    period_id = _seed_period(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        events = period_service.list_service_events(1, site_id, period_id)
        menu_context_service.sync_service_event_context(tenant_id=1, site_id=site_id, work_period_id=period_id, service_event_id=events[0].id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")
    response = client.post(
        "/offshore/work-menu/decisions",
        data={
            "work_period_id": str(period_id),
            "service_event_id": str(events[0].id),
            "menu_track_key": "fisk",
            "decision_type": "use_builder_composition",
            "selected_builder_composition_id": "does-not-exist",
        },
        headers=_headers("cook"),
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_offshore_work_menu_rejects_cross_tenant_request():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_builder_menu(app)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=TEST_WORK_MENU_DAY, builder_menu_id="builder-menu-1")
    _seed_period(app, tenant_id=1, site_id=site_id)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    response = client.get("/offshore/work-menu", headers=_headers("viewer", tenant_id=2))
    assert response.status_code in (302, 403)