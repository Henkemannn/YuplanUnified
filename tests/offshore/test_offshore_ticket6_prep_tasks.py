from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import CommunBuilderPublicationPin, Site, Tenant
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import (
    OffshoreInstallationSettings,
    OffshoreMenuCycle,
    OffshoreMenuCycleSlot,
    OffshorePeriodTemplate,
    OffshorePrepTask,
    OffshoreServiceEvent,
    OffshoreWorkPeriod,
    OffshoreWorkPosition,
)
from modules.offshore2.periods import _service as period_service
from modules.offshore2.prep_tasks import _service as prep_service


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


def _seed_period(app, *, tenant_id: int, site_id: str, start_iso: str, template_name: str = "Ops template", status: str = "planned"):
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
            assert position is not None
            template = period_service.create_period_template(
                tenant_id=tenant_id,
                site_id=site_id,
                name=template_name,
                duration_days=3,
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
                work_position_id=position.id,
                default_portions=24,
                active=True,
            )
            generation = period_service.create_work_period_from_template(
                tenant_id=tenant_id,
                site_id=site_id,
                period_template_id=template.id,
                starts_at=start_iso,
                menu_cycle_id=cycle.id,
                start_menu_cycle_slot_id=slot.id,
                name=template_name,
            )
            period_service.update_work_period(
                tenant_id=tenant_id,
                site_id=site_id,
                period_id=generation.work_period.id,
                payload={"status": status},
            )
            return generation
        finally:
            db.close()


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _upgrade_to_head(db_url: str) -> None:
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(_alembic_cfg(db_url), "head")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def _downgrade_to_revision(db_url: str, revision: str) -> None:
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.downgrade(_alembic_cfg(db_url), revision)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def test_offshore_prep_migration_upgrade_downgrade_roundtrip(tmp_path):
    db_path = tmp_path / "offshore_prep_migration.db"
    db_url = f"sqlite:///{db_path}"

    _upgrade_to_head(db_url)
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "offshore_prep_tasks" in tables
        assert inspector.get_foreign_keys("offshore_prep_tasks")
        indexes = {idx["name"] for idx in inspector.get_indexes("offshore_prep_tasks")}
        assert "ix_offshore_prep_tasks_tenant_site_date_status" in indexes
        assert "ix_offshore_prep_tasks_service_event_sort" in indexes
        assert "ix_offshore_prep_tasks_work_period_date" in indexes
        assert "ix_offshore_prep_tasks_work_position" in indexes
    finally:
        engine.dispose()

    _downgrade_to_revision(db_url, "0028_add_offshore_v2_menu_context")
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "offshore_prep_tasks" not in set(inspector.get_table_names())
    finally:
        engine.dispose()


def test_offshore_prep_route_create_transition_and_operations_integration():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20), builder_menu_id="builder-menu-1")
    generation = _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-07-20T08:00:00", status="active")

    with app.app_context():
        db = get_session()
        try:
            event = db.query(OffshoreServiceEvent).filter_by(tenant_id=1, site_id=site_id, work_period_id=generation.work_period.id).order_by(OffshoreServiceEvent.id.asc()).first()
            assert event is not None
            position = db.query(OffshoreWorkPosition).filter_by(tenant_id=1, site_id=site_id).first()
            assert position is not None
        finally:
            db.close()

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="cook")

    create_response = client.post(
        "/offshore/operations/prep/tasks",
        data={
            "service_event_id": str(event.id),
            "title": "Check oven",
            "instructions": "Warm up before service",
            "planned_date": "2026-07-20",
            "planned_time": "07:30",
            "work_position_id": str(position.id),
            "sort_order": "1",
            "component_name_snapshot": "Oven module",
        },
        headers=_headers("cook"),
    )
    assert create_response.status_code in (302, 303)

    with app.app_context():
        db = get_session()
        try:
            task = db.query(OffshorePrepTask).filter_by(service_event_id=event.id, title="Check oven").first()
            assert task is not None
            assert task.status == "planned"
            assert task.planned_date.isoformat() == "2026-07-20"
        finally:
            db.close()

    prep_page = client.get("/offshore/operations/prep?date=2026-07-20", headers=_headers("viewer"))
    assert prep_page.status_code == 200
    html = prep_page.get_data(as_text=True)
    assert "Check oven" in html
    assert "/offshore/periods/" in html

    transition_response = client.post(
        f"/offshore/operations/prep/tasks/{task.id}/transition",
        data={
            "status": "in_progress",
            "service_event_id": str(event.id),
            "planned_date": "2026-07-20",
            "expected_updated_at": task.updated_at.isoformat() if task.updated_at is not None else "",
        },
        headers=_headers("cook"),
    )
    assert transition_response.status_code in (302, 303)

    with app.app_context():
        db = get_session()
        try:
            updated = db.query(OffshorePrepTask).filter_by(id=task.id).first()
            assert updated is not None
            assert updated.status == "in_progress"
        finally:
            db.close()

    with app.app_context():
        vm = prep_service.build_day_view(
            tenant_id=1,
            site_id=site_id,
            selected_date=date(2026, 7, 20),
            locale="en",
            role="cook",
            user_id=42,
            focus_service_event_id=event.id,
        )
        assert vm.service_groups
        assert vm.summary.planned_count == 0
        assert vm.summary.in_progress_count == 1
        assert vm.service_groups[0].summary.in_progress_count == 1
        assert vm.service_groups[0].tasks[0].status == "in_progress"

        operations_vm = __import__("modules.offshore2.operations", fromlist=["_service"])._service.build_view_model(
            tenant_id=1,
            site_id=site_id,
            selected_date=date(2026, 7, 20),
            locale="en",
            theme="system",
            role="viewer",
            tenant_name="Tenant One",
            site_name="Rig A",
        )
        assert operations_vm["day"].services[0].prep_total_count == 1
        assert operations_vm["day"].services[0].prep_in_progress_count == 1


def test_offshore_service_event_prep_redirects_to_day_view():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_installation(app, tenant_id=1, site_id=site_id)
    generation = _seed_period(app, tenant_id=1, site_id=site_id, start_iso="2026-07-20T08:00:00", status="active")

    with app.app_context():
        db = get_session()
        try:
            event = db.query(OffshoreServiceEvent).filter_by(work_period_id=generation.work_period.id).order_by(OffshoreServiceEvent.id.asc()).first()
            assert event is not None
        finally:
            db.close()

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")
    response = client.get(f"/offshore/service-events/{event.id}/prep", headers=_headers("viewer"))
    assert response.status_code in (302, 303)
    assert "/offshore/operations/prep?" in response.headers.get("Location", "")
