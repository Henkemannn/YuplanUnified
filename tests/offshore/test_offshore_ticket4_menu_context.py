from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import CommunBuilderPublicationPin, Site, Tenant
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import (
    OffshoreMenuCycle,
    OffshoreMenuCycleSlot,
    OffshorePeriodTemplate,
    OffshorePeriodTemplateEvent,
    OffshoreServiceEventMenuContext,
    OffshoreWorkPosition,
)
from modules.offshore2.periods import _service as period_service


def _headers(role: str, tenant_id: int = 1):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": "42"}


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


def _seed_support_rows(app, *, tenant_id: int, site_id: str):
    with app.app_context():
        db = get_session()
        try:
            position = OffshoreWorkPosition(tenant_id=tenant_id, site_id=site_id, code="kokk", name="Kock", position_type="cook")
            cycle = OffshoreMenuCycle(tenant_id=tenant_id, site_id=site_id, name="Standard", cycle_length=4, is_active=True)
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


def _configure_installation_timezone(client, timezone: str = "Europe/Oslo"):
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


def _seed_publication(app, *, tenant_id: int, site_id: str, day: date, builder_menu_id: str = "builder-menu-1", builder_menu_version: int = 4):
    with app.app_context():
        db = get_session()
        try:
            iso = day.isocalendar()
            db.add(
                CommunBuilderPublicationPin(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=int(iso.year),
                    week=int(iso.week),
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_menu_version,
                    source="manual",
                )
            )
            db.commit()
        finally:
            db.close()


def _make_period_with_context(app, *, site_id: str, tenant_id: int = 1, start_menu_cycle_slot_id: int | None = None, period_status: str = "planned"):
    work_position_id, menu_cycle_id, menu_cycle_slot_id = _seed_support_rows(app, tenant_id=tenant_id, site_id=site_id)
    template = period_service.create_period_template(
        tenant_id=tenant_id,
        site_id=site_id,
        name="Menu context template",
        duration_days=2,
        active=True,
        sort_order=1,
    )
    period_service.add_template_event(
        tenant_id=tenant_id,
        site_id=site_id,
        template_id=template.id,
        day_offset="0",
        local_time=datetime.strptime("08:00", "%H:%M").time(),
        service_code="breakfast",
        display_name="Breakfast",
        work_position_id=work_position_id,
        default_portions=10,
        active=True,
    )
    generation = period_service.create_work_period_from_template(
        tenant_id=tenant_id,
        site_id=site_id,
        period_template_id=template.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=menu_cycle_id,
        start_menu_cycle_slot_id=start_menu_cycle_slot_id,
        name="Generated",
    )
    period_service.update_work_period(
        tenant_id=tenant_id,
        site_id=site_id,
        period_id=generation.work_period.id,
        payload={"status": period_status},
    )
    return generation, menu_cycle_id, menu_cycle_slot_id


def test_offshore_ticket4_generates_service_event_context_rows():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    work_position_id, menu_cycle_id, menu_cycle_slot_id = _seed_support_rows(app, tenant_id=1, site_id=site_id)
    client = app.test_client()

    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20))

    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = "admin"
        sess["full_name"] = "Henrik"

    _configure_installation_timezone(client)

    template = period_service.create_period_template(
        tenant_id=1,
        site_id=site_id,
        name="Menu context template",
        duration_days=2,
        active=True,
        sort_order=1,
    )
    period_service.add_template_event(
        tenant_id=1,
        site_id=site_id,
        template_id=template.id,
        day_offset="0",
        local_time=datetime.strptime("08:00", "%H:%M").time(),
        service_code="breakfast",
        display_name="Breakfast",
        work_position_id=work_position_id,
        default_portions=10,
        active=True,
    )

    generation = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_id,
        period_template_id=template.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=menu_cycle_id,
        name="Generated",
    )

    assert len(generation.service_events) == 1
    context = menu_context_service.resolve_context(
        tenant_id=1,
        site_id=site_id,
        work_period_id=generation.work_period.id,
        service_event_id=generation.service_events[0].id,
    )
    assert context.service_date == date(2026, 7, 20)
    assert context.menu_cycle_id == menu_cycle_id
    assert context.menu_cycle_slot_id == menu_cycle_slot_id
    assert context.menu_cycle_index == 1
    assert context.builder_publication_year == 2026
    assert context.builder_publication_week == 30
    assert context.builder_menu_id == "builder-menu-1"
    assert context.builder_menu_version == 4
    assert context.resolution_status == "resolved"
    assert context.assignment_source == "automatic"
    assert context.match_status == "matched"

    response = client.get(
        f"/offshore/periods/{generation.work_period.id}/service-events/{generation.service_events[0].id}/menu-context",
        headers=_headers("viewer"),
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["context"]["builder_menu_id"] == "builder-menu-1"
    assert body["context"]["menu_cycle_slot_id"] == menu_cycle_slot_id

    with app.app_context():
        db = get_session()
        try:
            rows = db.query(OffshoreServiceEventMenuContext).filter_by(tenant_id=1, site_id=site_id).all()
            assert len(rows) == 1
            assert rows[0].service_event_id == generation.service_events[0].id
            assert rows[0].builder_publication_pin_id is not None
        finally:
            db.close()

    repeat = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_id,
        period_template_id=template.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=menu_cycle_id,
        name="Generated again",
    )
    assert repeat.work_period.id == generation.work_period.id

    with app.app_context():
        db = get_session()
        try:
            assert db.query(OffshoreServiceEventMenuContext).filter_by(tenant_id=1, site_id=site_id).count() == 1
        finally:
            db.close()


def test_offshore_ticket4_manual_override_refresh_and_clear_rules():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = "admin"

    _configure_installation_timezone(client)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20))
    generation, _, _ = _make_period_with_context(app, site_id=site_id)
    event_id = generation.service_events[0].id

    manual = client.post(
        f"/offshore/periods/{generation.work_period.id}/service-events/{event_id}/menu-context/manual",
        data={"manual_note": "manual assignment"},
        headers=_headers("admin"),
    )
    assert manual.status_code == 200

    context = menu_context_service.get_context_for_event(
        tenant_id=1,
        site_id=site_id,
        work_period_id=generation.work_period.id,
        service_event_id=event_id,
    )
    assert context.resolution_status == "manual"
    assert context.assignment_source == "manual"

    refresh = client.post(
        f"/offshore/periods/{generation.work_period.id}/service-events/{event_id}/menu-context/refresh",
        headers=_headers("admin"),
    )
    assert refresh.status_code == 200
    context = menu_context_service.get_context_for_event(
        tenant_id=1,
        site_id=site_id,
        work_period_id=generation.work_period.id,
        service_event_id=event_id,
    )
    assert context.resolution_status == "manual"
    assert context.assignment_source == "manual"

    clear = client.post(
        f"/offshore/periods/{generation.work_period.id}/service-events/{event_id}/menu-context/clear",
        headers=_headers("admin"),
    )
    assert clear.status_code == 200
    context = menu_context_service.get_context_for_event(
        tenant_id=1,
        site_id=site_id,
        work_period_id=generation.work_period.id,
        service_event_id=event_id,
    )
    assert context.resolution_status == "resolved"
    assert context.assignment_source == "automatic"


def test_offshore_ticket4_permissions_dashboard_and_calendar_payload():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = "viewer"

    _configure_installation_timezone(client)
    dashboard = client.get("/offshore", headers=_headers("viewer"))
    assert dashboard.status_code == 200
    assert "Unresolved" in dashboard.get_data(as_text=True)
    assert "setup guidance" not in dashboard.get_data(as_text=True).lower()

    generation, _, _ = _make_period_with_context(app, site_id=site_id)
    payload = client.get(
        f"/offshore/periods/{generation.work_period.id}/service-events/{generation.service_events[0].id}/calendar-readiness",
        headers=_headers("viewer"),
    )
    assert payload.status_code == 200
    body = payload.get_json()
    assert body["source_module"] == "modules.offshore2"
    assert body["source_type"] == "service_event"
    assert body["menu_context_status"] == "unavailable"
    assert body["editable"] is False
    assert body["detail_url"].endswith(f"/offshore/periods/{generation.work_period.id}")

    forbidden = client.post(
        f"/offshore/periods/{generation.work_period.id}/service-events/{generation.service_events[0].id}/menu-context/refresh",
        headers=_headers("viewer"),
    )
    assert forbidden.status_code == 403


def test_offshore_ticket4_cycle_date_anchor_and_timezone_rules():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 1, 1))
    generation, _, _ = _make_period_with_context(app, site_id=site_id, start_menu_cycle_slot_id=None)
    context = menu_context_service.resolve_context(
        tenant_id=1,
        site_id=site_id,
        work_period_id=generation.work_period.id,
        service_event_id=generation.service_events[0].id,
    )
    assert context.service_date == date(2026, 7, 20)
    assert context.menu_cycle_index == 1
    assert context.start_menu_cycle_slot_id is not None


def test_offshore_ticket4_migration_roundtrip(tmp_path):
    db_path = tmp_path / "offshore_ticket4_migration.db"
    db_url = f"sqlite:///{db_path}"

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "0028_add_offshore_v2_menu_context")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "offshore_service_event_menu_contexts" in tables
        assert {column["name"] for column in inspector.get_columns("offshore_service_event_menu_contexts")} == {
            "id",
            "tenant_id",
            "site_id",
            "work_period_id",
            "service_event_id",
            "service_date",
            "menu_cycle_id",
            "start_menu_cycle_slot_id",
            "menu_cycle_slot_id",
            "menu_cycle_index",
            "service_key",
            "resolution_status",
            "assignment_source",
            "match_status",
            "resolution_reason",
            "manual_note",
            "builder_publication_pin_id",
            "builder_publication_year",
            "builder_publication_week",
            "builder_menu_id",
            "builder_menu_version",
            "created_at",
            "updated_at",
        }
        assert {column["name"] for column in inspector.get_columns("offshore_work_periods")} >= {
            "id",
            "tenant_id",
            "site_id",
            "period_template_id",
            "menu_cycle_id",
            "start_menu_cycle_slot_id",
            "name",
            "starts_at",
            "ends_at",
            "status",
            "notes",
            "created_at",
            "updated_at",
        }
        assert any(index["name"] == "ix_offshore_service_event_menu_contexts_tenant_site_status" for index in inspector.get_indexes("offshore_service_event_menu_contexts"))
        assert any(index["name"] == "ix_offshore_service_event_menu_contexts_tenant_site_date" for index in inspector.get_indexes("offshore_service_event_menu_contexts"))
        with engine.begin() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_service_event_menu_contexts")).scalar_one() == 0
    finally:
        engine.dispose()

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.downgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "0027_add_offshore_v2_periods")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "offshore_service_event_menu_contexts" not in tables
        assert "start_menu_cycle_slot_id" not in {column["name"] for column in inspector.get_columns("offshore_work_periods")}
    finally:
        engine.dispose()

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "0028_add_offshore_v2_menu_context")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "offshore_service_event_menu_contexts" in set(inspector.get_table_names())
    finally:
        engine.dispose()