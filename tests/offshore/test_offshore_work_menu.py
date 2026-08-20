from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from core.app_factory import create_app
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


def _headers(role: str, tenant_id: int = 1):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": "42", "X-User-Name": "Henrik"}


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
        flow.create_standalone_component("Demo Offshore Kött")
        flow.create_standalone_component("Demo Offshore Fisk")
        flow.create_standalone_component("Demo Offshore Soppa")
        flow.create_standalone_component("Demo Offshore Vegetariskt")
        for composition_id, composition_name in [
            ("demo_offshore_kott", "Demo Offshore Kött"),
            ("demo_offshore_fisk", "Demo Offshore Fisk"),
            ("demo_offshore_soppa", "Demo Offshore Soppa"),
            ("demo_offshore_vegetariskt", "Demo Offshore Vegetariskt"),
        ]:
            if flow._composition_repository.get(composition_id) is None:
                flow.create_composition(composition_id, composition_name, library_group="demo-offshore")
            flow.add_component_to_composition(
                composition_id=composition_id,
                component_name=composition_name,
                role="main",
            )
        menu_flow.create_menu(menu_id=menu_id, site_id="demo-site", week_key="demo-week", title="Demo Offshore Builder Menu", version=1, status="draft")
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            for meal_slot in ("lunch", "dinner"):
                for sort_order, composition_id in enumerate(("demo_offshore_kott", "demo_offshore_fisk", "demo_offshore_soppa", "demo_offshore_vegetariskt"), start=1):
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
    assert "/builder-editor-host?composition_id=demo_offshore_kott" in html
    assert "offshore-work-menu-meal__status" not in html
    assert "offshore-work-menu-meal__meta" not in html

    assert "data-work-menu-builder-open" in html
    assert "data-work-menu-builder-host" in html
    assert "offshore-work-menu-builder-host__backdrop" in html
    assert "offshore-work-menu-builder-host__frame" in html
    assert 'src="/builder-editor-host"' in html
    assert 'src="about:blank"' not in html
    assert 'target="_blank"' not in html
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
        )

    first_day = (vm.get("days") or [])[0]
    first_meal = (first_day.meals or [])[0]
    first_track = (first_meal.tracks or [])[0]
    assert first_track.builder_bridge is not None
    assert first_track.builder_bridge["composition_name"] == "Demo Offshore Kött"
    assert first_track.builder_bridge["component_count"] == 1
    assert [item["component_name"] for item in first_track.builder_bridge["components"]] == ["Demo Offshore Kött"]
    assert first_track.builder_bridge["builder_url"].startswith("/builder-editor-host?composition_id=")

    js_path = "static/offshore2/work_menu.js"
    with open(js_path, encoding="utf-8") as f:
        js_source = f.read()
    assert "if (openBuilderHostFromTrack(row)) {" in js_source
    assert "event.preventDefault();" in js_source
    assert "event.stopPropagation();" in js_source
    assert js_source.index("openBuilderHostFromTrack(row)") < js_source.index("openModalFromTrack(row)")
    assert "event.target.closest('[data-work-menu-builder-open]')" not in js_source
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
    assert "String(detail.kind || '') !== lastBuilderHostKind" in js_source
    assert "builder-host-ready" in js_source
    assert "offshore-work-menu-builder-host--ready" in js_source
    assert "offshore-work-menu-builder-host--open" in js_source
    assert "window.scrollTo(lastBuilderHostScrollX, lastBuilderHostScrollY);" in js_source

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
        follow_redirects=True,
    )
    assert post.status_code == 200

    with app.app_context():
        db = get_session()
        try:
            after = db.query(OffshoreWorkMenuDecision).count()
        finally:
            db.close()
    assert after == before + 1


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