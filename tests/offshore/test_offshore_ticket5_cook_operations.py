from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import CommunBuilderPublicationPin, Site, Tenant
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import (
    OffshoreInstallationSettings,
    OffshoreMenuCycle,
    OffshoreMenuCycleSlot,
    OffshorePeriodTemplate,
    OffshoreServiceEvent,
    OffshoreServiceEventMenuContext,
    OffshoreWorkPeriod,
    OffshoreWorkPosition,
)
from modules.offshore2.operations import _service as operations_service
from modules.offshore2.periods import _service as period_service


def _headers(role: str, tenant_id: int = 1):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": "42"}


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


def _seed_installation(app, *, tenant_id: int, site_id: str, timezone: str = "Europe/Oslo") -> None:
    with app.app_context():
        db = get_session()
        try:
            db.merge(
                OffshoreInstallationSettings(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    timezone=timezone,
                    default_locale="sv",
                    default_theme="system",
                    default_portions=120,
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


def _seed_support_rows(app, *, tenant_id: int, site_id: str):
    with app.app_context():
        db = get_session()
        try:
            position = OffshoreWorkPosition(tenant_id=tenant_id, site_id=site_id, code=f"kokk-{uuid.uuid4().hex[:6]}", name="Kock", position_type="cook")
            cycle = OffshoreMenuCycle(tenant_id=tenant_id, site_id=site_id, name="Cycle", cycle_length=4, is_active=True)
            db.add(position)
            db.add(cycle)
            db.commit()
            db.refresh(position)
            db.refresh(cycle)
            slot = OffshoreMenuCycleSlot(tenant_id=tenant_id, site_id=site_id, menu_cycle_id=cycle.id, cycle_index=1, label="Slot 1")
            db.add(slot)
            db.commit()
            db.refresh(slot)
            return position.id, cycle.id, slot.id
        finally:
            db.close()


def _seed_period(app, *, tenant_id: int, site_id: str, start_iso: str, template_name: str = "Ops template", status: str = "planned", include_events: bool = True):
    position_id, menu_cycle_id, slot_id = _seed_support_rows(app, tenant_id=tenant_id, site_id=site_id)
    template = period_service.create_period_template(
        tenant_id=tenant_id,
        site_id=site_id,
        name=template_name,
        duration_days=3,
        active=True,
        sort_order=1,
    )
    if include_events:
        period_service.add_template_event(
            tenant_id=tenant_id,
            site_id=site_id,
            template_id=template.id,
            day_offset="0",
            local_time=datetime.strptime("08:00", "%H:%M").time(),
            service_code="breakfast",
            display_name="Breakfast",
            work_position_id=position_id,
            default_portions=24,
            active=True,
        )
        period_service.add_template_event(
            tenant_id=tenant_id,
            site_id=site_id,
            template_id=template.id,
            day_offset="1",
            local_time=datetime.strptime("12:00", "%H:%M").time(),
            service_code="lunch",
            display_name="Lunch",
            work_position_id=position_id,
            default_portions=18,
            active=True,
        )
    generation = period_service.create_work_period_from_template(
        tenant_id=tenant_id,
        site_id=site_id,
        period_template_id=template.id,
        starts_at=start_iso,
        menu_cycle_id=menu_cycle_id,
        start_menu_cycle_slot_id=slot_id,
        name=template_name,
    )
    period_service.update_work_period(
        tenant_id=tenant_id,
        site_id=site_id,
        period_id=generation.work_period.id,
        payload={"status": status},
    )
    return generation


def _seed_menu_context(app, *, tenant_id: int, site_id: str, period_id: int, event_id: int):
    return menu_context_service.sync_service_event_context(
        tenant_id=tenant_id,
        site_id=site_id,
        work_period_id=period_id,
        service_event_id=event_id,
    )


def _configure_installation(client, timezone: str = "Europe/Oslo"):
    return client.post(
        "/offshore/settings/installation",
        data={
            "timezone": timezone,
            "default_locale": "sv",
            "default_theme": "system",
            "default_portions": "120",
            "is_active": "1",
        },
        headers=_headers("admin"),
    )


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_offshore_operations_access_scope_and_dashboard_entry():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20), builder_menu_id="builder-menu-1")
    _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-07-20T08:00:00", status="active")

    client = app.test_client()
    unauthenticated = client.get("/offshore/operations")
    assert unauthenticated.status_code in (401, 403)

    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    viewer = client.get("/offshore/operations", headers=_headers("viewer"))
    assert viewer.status_code == 200
    assert "Dagens tjänster" in viewer.get_data(as_text=True) or "Today's services" in viewer.get_data(as_text=True)

    _login(client, tenant_id=1, site_id=site_id, role="admin")
    admin = client.get("/offshore/operations", headers=_headers("admin"))
    assert admin.status_code == 200
    assert "Dagens tjänster" in admin.get_data(as_text=True) or "Today's services" in admin.get_data(as_text=True)

    current_day = client.get("/offshore/operations?date=2026-07-20", headers=_headers("admin"))
    assert current_day.status_code == 200
    assert "/offshore/periods/" in current_day.get_data(as_text=True)

    dashboard = client.get("/offshore", headers=_headers("admin"))
    assert dashboard.status_code == 200
    assert "/offshore/operations" in dashboard.get_data(as_text=True)

    wrong_tenant = client.get("/offshore/operations", headers=_headers("admin", tenant_id=2))
    assert wrong_tenant.status_code in (302, 403)


def test_offshore_operations_invalid_date_redirects_cleanly_and_defaults_to_local_today():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")

    invalid = client.get("/offshore/operations?date=2026-99-99", headers=_headers("viewer"))
    assert invalid.status_code in (302, 303)
    assert "/offshore/operations" in invalid.headers.get("Location", "")

    view = client.get("/offshore/operations", headers=_headers("viewer"))
    assert view.status_code == 200
    assert "Selected date" in view.get_data(as_text=True) or "Valt datum" in view.get_data(as_text=True)


def test_offshore_operations_period_resolution_day_services_and_menu_context_states():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20), builder_menu_id="builder-menu-1")
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 27), builder_menu_id="builder-menu-2")

    active_period = _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-07-20T08:00:00", status="active")
    upcoming_period = _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-07-27T08:00:00", status="planned", template_name="Upcoming period")
    with app.app_context():
        db = get_session()
        try:
            event_rows = db.query(OffshoreServiceEvent).filter_by(tenant_id=1, site_id=site_id, work_period_id=active_period.work_period.id).order_by(OffshoreServiceEvent.id.asc()).all()
            assert len(event_rows) == 2
            resolved = _seed_menu_context(app, tenant_id=1, site_id=site_id, period_id=active_period.work_period.id, event_id=event_rows[0].id)
            assert resolved.resolution_status == "resolved"
            db.query(OffshoreServiceEventMenuContext).filter_by(tenant_id=1, site_id=site_id, service_event_id=event_rows[1].id).delete()
            db.commit()
        finally:
            db.close()

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")

    current_day = client.get("/offshore/operations?date=2026-07-20", headers=_headers("viewer"))
    assert current_day.status_code == 200
    html = current_day.get_data(as_text=True)
    assert "Breakfast" in html
    assert "Lunch" in html
    assert "builder-menu-1" in html

    with app.app_context():
        vm = operations_service.build_view_model(tenant_id=1, site_id=site_id, selected_date=date(2026, 7, 20), locale="en", theme="system", role="viewer", tenant_name="Tenant One", site_name="Rig A")
        assert vm["day"].service_count == 1
        assert vm["day"].services[0].has_menu_context is True
        assert any(item.service_label == "Lunch" and item.has_menu_context is False and item.menu_context_status is None for day in vm["upcoming_days"] for item in day.services)

    upcoming_day = client.get("/offshore/operations?date=2026-07-24", headers=_headers("viewer"))
    assert upcoming_day.status_code == 200
    upcoming_html = upcoming_day.get_data(as_text=True)
    assert "Upcoming period" in upcoming_html or "Kommande arbetsperiod" in upcoming_html


def test_offshore_operations_timezone_and_dst_local_date_conversion():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id, timezone="Europe/Oslo")
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 3, 29), builder_menu_id="builder-menu-1")
    period = _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-03-29T03:00:00", status="active")

    with app.app_context():
        db = get_session()
        try:
            event = db.query(OffshoreServiceEvent).filter_by(work_period_id=period.work_period.id).order_by(OffshoreServiceEvent.id.asc()).first()
            assert event is not None
        finally:
            db.close()

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    response = client.get("/offshore/operations?date=2026-03-29", headers=_headers("viewer"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "2026-03-29" in html

    vm = operations_service.build_view_model(tenant_id=1, site_id=site_id, selected_date=date(2026, 3, 29), locale="en", theme="system", role="viewer", tenant_name="Tenant One", site_name="Rig A")
    assert vm["day"].services[0].calendar_item.starts_at.tzinfo is UTC
    assert vm["day"].services[0].calendar_item.starts_at.isoformat().endswith("+00:00")
    assert vm["day"].services[0].local_date == "2026-03-29"


def test_offshore_operations_no_installation_no_period_and_empty_states_are_safe():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")

    no_installation = client.get("/offshore/operations", headers=_headers("viewer"))
    assert no_installation.status_code == 200
    assert "Skapa installationsinställningar" in no_installation.get_data(as_text=True) or "Create installation settings" in no_installation.get_data(as_text=True)

    _seed_installation(app, tenant_id=1, site_id=site_id)
    with app.app_context():
        vm = operations_service.build_view_model(tenant_id=1, site_id=site_id, selected_date=date(2026, 7, 21), locale="en", theme="system", role="viewer", tenant_name="Tenant One", site_name="Rig A")
        assert vm["state_key"] == "no_applicable_period"
        assert vm["day"].service_count == 0


def test_offshore_operations_no_migration_and_no_persistent_calendar_rows():
    from core.models import Base

    assert not any("operations" in name.lower() for name in Base.metadata.tables)
    assert not any("calendar" in name.lower() for name in Base.metadata.tables)

    migration_dir = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    assert not any("operations" in path.name.lower() for path in migration_dir.glob("*.py"))
