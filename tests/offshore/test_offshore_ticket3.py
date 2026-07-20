from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Site, Tenant
from modules.offshore2.models import OffshoreInstallationSettings, OffshoreMenuCycle, OffshorePeriodTemplate, OffshorePeriodTemplateEvent, OffshoreServiceEvent, OffshoreWorkPeriod, OffshoreWorkPosition
from modules.offshore2.periods import _service as period_service, site_timezone_name


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


def _login(client, *, tenant_id: int, site_id: str, role: str):
    with client.session_transaction() as sess:
        sess["tenant_id"] = tenant_id
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = role
        sess["full_name"] = "Henrik"


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


def _seed_period_support_rows(app, *, tenant_id: int, site_id: str):
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
            return position.id, cycle.id
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


def test_offshore_ticket3_period_pages_and_generation():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    work_position_id, menu_cycle_id = _seed_period_support_rows(app, tenant_id=1, site_id=site_id)
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")
    _configure_installation_timezone(client)

    assert site_timezone_name(1, site_id) == "Europe/Oslo"

    page = client.get("/offshore/period-templates", headers=_headers("admin"))
    assert page.status_code == 200
    assert "name=\"duration_days\"" in page.get_data(as_text=True)
    assert "Det finns inga periodmallar än." in page.get_data(as_text=True)

    empty_periods = client.get("/offshore/periods", headers=_headers("admin"))
    assert empty_periods.status_code == 200
    assert "Det finns inga arbetsperioder än." in empty_periods.get_data(as_text=True)

    response = client.post(
        "/offshore/period-templates",
        data={
            "name": "Bemanningsmall",
            "duration_days": "3",
            "start_weekday": "1",
            "description": "Base template",
            "active": "1",
            "sort_order": "2",
        },
        headers=_headers("admin"),
    )
    assert response.status_code == 302

    template = period_service.create_period_template(
        tenant_id=1,
        site_id=site_id,
        name="Kontraktsmall",
        duration_days=3,
        description="Base template",
        start_weekday=4,
        active=True,
        sort_order=3,
    )
    active_event = period_service.add_template_event(
        tenant_id=1,
        site_id=site_id,
        template_id=template.id,
        day_offset=1,
        local_time=datetime.strptime("06:15", "%H:%M").time(),
        service_code="breakfast",
        display_name="Frukost",
        work_position_id=work_position_id,
        default_portions=24,
        notes="Morning service",
        sort_order=1,
        active=True,
    )
    period_service.add_template_event(
        tenant_id=1,
        site_id=site_id,
        template_id=template.id,
        day_offset=2,
        local_time=datetime.strptime("07:30", "%H:%M").time(),
        service_code="lunch",
        display_name="Lunch",
        work_position_id=work_position_id,
        default_portions=18,
        notes="Inactive snapshot",
        sort_order=2,
        active=False,
    )

    with app.app_context():
        db = get_session()
        try:
            template_row = db.query(OffshorePeriodTemplate).filter_by(id=template.id, tenant_id=1, site_id=site_id).one()
            assert template_row.duration_days == 3
        finally:
            db.close()

    detail = client.get(f"/offshore/period-templates/{template.id}", headers=_headers("admin"))
    assert detail.status_code == 200
    html = detail.get_data(as_text=True)
    assert "Frukost" in html
    assert "Dag 2" in html or "Day 2" in html

    period_response = client.post(
        "/offshore/periods",
        data={
            "period_template_id": str(template.id),
            "start_date": "2026-07-20",
            "start_time": "08:00",
            "name": "Period A",
            "menu_cycle_id": str(menu_cycle_id),
            "notes": "Generated from template",
        },
        headers=_headers("admin"),
    )
    assert period_response.status_code == 302

    period_detail = client.get("/offshore/periods/1", headers=_headers("admin"))
    assert period_detail.status_code == 200
    period_html = period_detail.get_data(as_text=True)
    assert "Period A" in period_html
    assert "Frukost" in period_html
    assert "name=\"start_time\"" in period_html

    with app.app_context():
        db = get_session()
        try:
            period = db.query(OffshoreWorkPeriod).filter_by(tenant_id=1, site_id=site_id).one()
            events = db.query(OffshoreServiceEvent).filter_by(tenant_id=1, site_id=site_id).order_by(OffshoreServiceEvent.id.asc()).all()
            assert len(events) == 1
            period_id = period.id
            event_id = events[0].id
            stored_period = db.execute(
                text("SELECT starts_at, ends_at FROM offshore_work_periods WHERE id = :period_id"),
                {"period_id": period_id},
            ).fetchone()
            assert str(stored_period[0]).startswith("2026-07-20 06:00")
            assert str(stored_period[1]).startswith("2026-07-23 06:00")
            assert period.ends_at - period.starts_at == timedelta(days=3)
            stored_event = db.execute(
                text("SELECT starts_at, source_template_event_id, expected_portions, status, display_name, service_code FROM offshore_service_events WHERE id = :event_id"),
                {"event_id": event_id},
            ).fetchone()
            assert stored_event[1] == active_event.id
            assert str(stored_event[0]).startswith("2026-07-21 04:15")
            assert events[0].display_name == "Frukost"
            assert events[0].service_code == "breakfast"
            assert events[0].expected_portions == 24
            assert events[0].status == "planned"

            dst_period = period_service.create_work_period(
                tenant_id=1,
                site_id=site_id,
                name="DST period",
                starts_at="2026-03-29T03:30:00",
                ends_at="2026-03-29T04:30:00",
                status="draft",
            )
            dst_row = db.execute(
                text("SELECT starts_at FROM offshore_work_periods WHERE id = :period_id"),
                {"period_id": dst_period.id},
            ).fetchone()
            assert str(dst_row[0]).startswith("2026-03-29 01:30")
        finally:
            db.close()

    period_service.update_template_event(
        tenant_id=1,
        site_id=site_id,
        template_id=template.id,
        event_id=active_event.id,
        payload={
            "display_name": "Frukost uppdaterad",
            "service_code": "breakfast",
            "day_offset": 1,
            "local_time": "06:15",
        },
    )
    period_service.update_period_template(
        tenant_id=1,
        site_id=site_id,
        template_id=template.id,
        name="Kontraktsmall",
        duration_days=5,
        description="Edited template",
        start_weekday=4,
        active=True,
        sort_order=3,
    )

    with app.app_context():
        db = get_session()
        try:
            period = db.query(OffshoreWorkPeriod).filter_by(id=period_id, tenant_id=1, site_id=site_id).one()
            event = db.query(OffshoreServiceEvent).filter_by(id=event_id, tenant_id=1, site_id=site_id).one()
            stored_period = db.execute(
                text("SELECT ends_at FROM offshore_work_periods WHERE id = :period_id"),
                {"period_id": period.id},
            ).fetchone()
            assert str(stored_period[0]).startswith("2026-07-23 06:00")
            assert event.display_name == "Frukost"
            assert event.service_code == "breakfast"
            assert event.expected_portions == 24
        finally:
            db.close()

    repeat = client.post(
        "/offshore/periods",
        data={
            "period_template_id": str(template.id),
            "start_date": "2026-07-20",
            "start_time": "08:00",
            "name": "Period A",
            "menu_cycle_id": str(menu_cycle_id),
            "notes": "Generated from template",
        },
        headers=_headers("admin"),
    )
    assert repeat.status_code == 302
    assert repeat.headers["Location"].endswith("/offshore/periods/1")

    with app.app_context():
        db = get_session()
        try:
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM offshore_work_periods "
                    "WHERE tenant_id=1 AND site_id=:sid AND period_template_id=:template_id AND menu_cycle_id=:menu_cycle_id"
                ),
                {"sid": site_id, "template_id": template.id, "menu_cycle_id": menu_cycle_id},
            ).scalar_one() == 1
            assert db.execute(text("SELECT COUNT(*) FROM offshore_service_events WHERE tenant_id=1 AND site_id=:sid"), {"sid": site_id}).scalar_one() == 1
        finally:
            db.close()


def test_offshore_ticket3_generation_rolls_back_invalid_template_event():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    _seed_period_support_rows(app, tenant_id=1, site_id=site_id)
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")
    _configure_installation_timezone(client)

    template = period_service.create_period_template(
        tenant_id=1,
        site_id=site_id,
        name="Rollbackmall",
        duration_days=1,
        active=True,
        sort_order=1,
    )

    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO offshore_period_template_events "
                    "(tenant_id, site_id, period_template_id, day_offset, local_time, service_code, display_name, sort_order, active, created_at, updated_at) "
                    "VALUES (:tenant_id, :site_id, :template_id, :day_offset, :local_time, :service_code, :display_name, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "tenant_id": 1,
                    "site_id": site_id,
                    "template_id": template.id,
                    "day_offset": 1,
                    "local_time": "08:00:00",
                    "service_code": "breakfast",
                    "display_name": "Frukost",
                },
            )
            db.commit()
        finally:
            db.close()


def test_offshore_ticket3_generation_idempotency_key_variants():
    app = _mk_app()
    site_a = _seed_site(app, tenant_id=1, name="Rig A")
    site_b = _seed_site(app, tenant_id=1, name="Rig B")
    position_a, cycle_a = _seed_period_support_rows(app, tenant_id=1, site_id=site_a)
    position_b, cycle_b = _seed_period_support_rows(app, tenant_id=1, site_id=site_b)
    with app.app_context():
        db = get_session()
        try:
            cycle_a2 = OffshoreMenuCycle(tenant_id=1, site_id=site_a, name="Standard 2", cycle_length=4, is_active=True)
            db.add(cycle_a2)
            db.commit()
            db.refresh(cycle_a2)
            cycle_a2_id = cycle_a2.id
        finally:
            db.close()

    template_a = period_service.create_period_template(
        tenant_id=1,
        site_id=site_a,
        name="Idempotent A",
        duration_days=2,
        active=True,
        sort_order=1,
    )
    period_service.add_template_event(
        tenant_id=1,
        site_id=site_a,
        template_id=template_a.id,
        day_offset="0",
        local_time=datetime.strptime("08:00", "%H:%M").time(),
        service_code="breakfast",
        display_name="Breakfast A",
        work_position_id=position_a,
        default_portions=10,
        active=True,
    )

    template_b = period_service.create_period_template(
        tenant_id=1,
        site_id=site_b,
        name="Idempotent B",
        duration_days=2,
        active=True,
        sort_order=1,
    )
    period_service.add_template_event(
        tenant_id=1,
        site_id=site_b,
        template_id=template_b.id,
        day_offset="0",
        local_time=datetime.strptime("08:00", "%H:%M").time(),
        service_code="breakfast",
        display_name="Breakfast B",
        work_position_id=position_b,
        default_portions=10,
        active=True,
    )

    first = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_a,
        period_template_id=template_a.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=cycle_a,
        name="Same start one",
    )
    repeat = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_a,
        period_template_id=template_a.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=cycle_a,
        name="Same start two",
    )
    later = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_a,
        period_template_id=template_a.id,
        starts_at="2026-07-27T08:00:00",
        menu_cycle_id=cycle_a,
        name="Different start",
    )
    other_site = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_b,
        period_template_id=template_b.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=cycle_b,
        name="Other site",
    )
    different_cycle = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_a,
        period_template_id=template_a.id,
        starts_at="2026-07-20T08:00:00",
        menu_cycle_id=cycle_a2_id,
        name="Different cycle",
    )

    assert repeat.work_period.id == first.work_period.id
    assert [event.id for event in repeat.service_events] == [event.id for event in first.service_events]
    assert later.work_period.id != first.work_period.id
    assert other_site.work_period.id != first.work_period.id
    assert different_cycle.work_period.id != first.work_period.id
    assert different_cycle.work_period.id != later.work_period.id

    with app.app_context():
        db = get_session()
        try:
            site_a_periods = (
                db.query(OffshoreWorkPeriod)
                .filter_by(tenant_id=1, site_id=site_a, period_template_id=template_a.id, menu_cycle_id=cycle_a)
                .order_by(OffshoreWorkPeriod.starts_at.asc(), OffshoreWorkPeriod.id.asc())
                .all()
            )
            site_b_periods = db.query(OffshoreWorkPeriod).filter_by(tenant_id=1, site_id=site_b, period_template_id=template_b.id).all()
            site_a_events = db.query(OffshoreServiceEvent).filter_by(tenant_id=1, site_id=site_a).all()
            site_b_events = db.query(OffshoreServiceEvent).filter_by(tenant_id=1, site_id=site_b).all()

            assert len(site_a_periods) == 2
            assert len(site_b_periods) == 1
            assert len(site_a_events) == 3
            assert len(site_b_events) == 1
            assert site_a_periods[0].id == first.work_period.id
            assert site_a_periods[1].id == later.work_period.id
            assert site_b_periods[0].id == other_site.work_period.id
        finally:
            db.close()


def test_offshore_ticket3_invariants_overlap_authorization_and_scope():
    app = _mk_app()
    site_a = _seed_site(app, tenant_id=1, name="Rig A")
    site_b = _seed_site(app, tenant_id=2, name="Rig B")
    pos_a, cycle_a = _seed_period_support_rows(app, tenant_id=1, site_id=site_a)
    pos_b, cycle_b = _seed_period_support_rows(app, tenant_id=2, site_id=site_b)

    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_a, role="viewer")

    viewer_read = client.get("/offshore/period-templates", headers=_headers("viewer"))
    assert viewer_read.status_code == 200
    assert "Det finns inga periodmallar än." in viewer_read.get_data(as_text=True)

    viewer_write = client.post("/offshore/period-templates", data={"name": "Viewer", "duration_days": "1"}, headers=_headers("viewer"))
    assert viewer_write.status_code == 403

    admin_client = app.test_client()
    _login(admin_client, tenant_id=1, site_id=site_a, role="admin")
    superuser_client = app.test_client()
    _login(superuser_client, tenant_id=1, site_id=site_a, role="superuser")
    editor_client = app.test_client()
    _login(editor_client, tenant_id=1, site_id=site_a, role="editor")

    assert superuser_client.get("/offshore", headers=_headers("superuser")).status_code == 200

    with pytest.raises(ValueError, match="offshore.validation.invalid_duration_days"):
        period_service.create_period_template(tenant_id=1, site_id=site_a, name="Bad", duration_days=0)

    template_a = period_service.create_period_template(tenant_id=1, site_id=site_a, name="A", duration_days=2, active=True, sort_order=1)
    template_b = period_service.create_period_template(tenant_id=2, site_id=site_b, name="B", duration_days=2, active=True, sort_order=1)

    with pytest.raises(ValueError, match="offshore.validation.invalid_day_offset"):
        period_service.add_template_event(
            tenant_id=1,
            site_id=site_a,
            template_id=template_a.id,
            day_offset=-1,
            local_time=datetime.strptime("08:00", "%H:%M").time(),
            service_code="breakfast",
            display_name="Frukost",
        )

    with pytest.raises(ValueError, match="offshore.validation.invalid_day_offset"):
        period_service.add_template_event(
            tenant_id=1,
            site_id=site_a,
            template_id=template_a.id,
            day_offset=2,
            local_time=datetime.strptime("08:00", "%H:%M").time(),
            service_code="breakfast",
            display_name="Frukost",
        )

    event = period_service.add_template_event(
        tenant_id=1,
        site_id=site_a,
        template_id=template_a.id,
        day_offset="0",
        local_time=datetime.strptime("08:00", "%H:%M").time(),
        service_code="breakfast",
        display_name="Frukost",
        work_position_id=pos_a,
        default_portions=12,
    )

    with pytest.raises(ValueError, match="offshore.validation.duplicate_template_event"):
        period_service.add_template_event(
            tenant_id=1,
            site_id=site_a,
            template_id=template_a.id,
            day_offset="0",
            local_time=datetime.strptime("08:00", "%H:%M").time(),
            service_code="breakfast",
            display_name="Frukost",
            work_position_id=pos_a,
            default_portions=12,
        )

    with pytest.raises(LookupError, match="offshore.validation.cross_site"):
        period_service.add_template_event(
            tenant_id=1,
            site_id=site_a,
            template_id=template_a.id,
            day_offset=1,
            local_time=datetime.strptime("08:00", "%H:%M").time(),
            service_code="breakfast2",
            display_name="Frukost 2",
            work_position_id=pos_b,
        )

    with pytest.raises(LookupError, match="offshore.validation.cross_site"):
        period_service.create_work_period_from_template(
            tenant_id=1,
            site_id=site_a,
            period_template_id=template_b.id,
            starts_at="2026-07-20T08:00:00",
            name="Wrong template",
        )

    with pytest.raises(LookupError, match="offshore.validation.cross_site"):
        period_service.create_work_period_from_template(
            tenant_id=1,
            site_id=site_a,
            period_template_id=template_a.id,
            starts_at="2026-07-20T08:00:00",
            menu_cycle_id=cycle_b,
            name="Wrong cycle",
        )

    with pytest.raises(LookupError, match="offshore.validation.cross_site"):
        period_service.list_period_templates(tenant_id=2, site_id=site_a)

    with pytest.raises(LookupError, match="offshore.validation.cross_site"):
        period_service.create_period_template(tenant_id=2, site_id=site_a, name="Cross tenant", duration_days=1)

    with pytest.raises(ValueError, match="offshore.validation.invalid_period_range"):
        period_service.create_work_period(
            tenant_id=1,
            site_id=site_a,
            name="Bad range",
            starts_at="2026-07-20T10:00:00",
            ends_at="2026-07-20T09:00:00",
        )

    period1 = period_service.create_work_period(
        tenant_id=1,
        site_id=site_a,
        name="Overlap One",
        starts_at="2026-07-20T08:00:00",
        ends_at="2026-07-22T08:00:00",
        menu_cycle_id=cycle_a,
    )
    period2 = period_service.create_work_period(
        tenant_id=1,
        site_id=site_a,
        name="Overlap Two",
        starts_at="2026-07-21T08:00:00",
        ends_at="2026-07-23T08:00:00",
        menu_cycle_id=cycle_a,
    )
    assert period1.id != period2.id

    overlaps = period_service.detect_period_overlaps(tenant_id=1, site_id=site_a)
    assert len(overlaps) == 1
    assert overlaps[0]["left"].name == "Overlap One"
    assert overlaps[0]["right"].name == "Overlap Two"

    dashboard = admin_client.get("/offshore", headers=_headers("admin"))
    assert dashboard.status_code == 200
    dashboard_html = dashboard.get_data(as_text=True)
    assert "Overlap One" in dashboard_html
    assert "Overlap Two" in dashboard_html
    assert "↔" in dashboard_html

    generated_period = period_service.create_work_period_from_template(
        tenant_id=1,
        site_id=site_a,
        period_template_id=template_a.id,
        starts_at="2026-07-24T08:00:00",
        menu_cycle_id=cycle_a,
        name="Generated",
    )
    generated_event = generated_period.service_events[0]
    with pytest.raises(ValueError, match="offshore.validation.invalid_portions"):
        period_service.update_service_event(
            tenant_id=1,
            site_id=site_a,
            work_period_id=generated_period.work_period.id,
            event_id=generated_event.id,
            payload={"expected_portions": -1},
        )

    editor_write = editor_client.post(
        "/offshore/periods",
        data={
            "period_template_id": str(template_a.id),
            "start_date": "2026-07-24",
            "start_time": "08:00",
            "name": "Editor period",
            "menu_cycle_id": str(cycle_a),
        },
        headers=_headers("editor"),
    )
    assert editor_write.status_code == 302

    admin_template_write = admin_client.post(
        "/offshore/period-templates",
        data={"name": "Admin template", "duration_days": "1", "active": "1"},
        headers=_headers("admin"),
    )
    assert admin_template_write.status_code == 302

    cross_site_read = app.test_client()
    _login(cross_site_read, tenant_id=1, site_id=site_b, role="admin")
    cross_site_response = cross_site_read.get(f"/offshore/periods/{period1.id}", headers=_headers("admin"))
    assert cross_site_response.status_code == 302
    assert "/ui/select-site" in cross_site_response.headers["Location"]

    feature_flag_off = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with feature_flag_off.app_context():
        create_all()
    feature_flag_off.feature_registry.set("offshore.v2.enabled", False)
    off_client = feature_flag_off.test_client()
    assert off_client.get("/offshore", headers=_headers("admin")).status_code == 404


def test_offshore_ticket3_empty_pages_and_feature_flag_gate():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    templates_page = client.get("/offshore/period-templates", headers=_headers("admin"))
    periods_page = client.get("/offshore/periods", headers=_headers("admin"))
    assert templates_page.status_code == 200
    assert periods_page.status_code == 200
    assert "Det finns inga periodmallar än." in templates_page.get_data(as_text=True)
    assert "Det finns inga arbetsperioder än." in periods_page.get_data(as_text=True)


def test_offshore_ticket3_migration_roundtrip(tmp_path):
    db_path = tmp_path / "offshore_ticket3_migration.db"
    db_url = f"sqlite:///{db_path}"

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(_alembic_cfg(db_url), "0026_add_offshore_v2_installation_settings")
        command.upgrade(_alembic_cfg(db_url), "0027_add_offshore_v2_periods")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"offshore_installation_settings", "offshore_work_positions", "offshore_menu_cycles", "offshore_menu_cycle_slots", "offshore_period_templates", "offshore_period_template_events", "offshore_work_periods", "offshore_service_events"}.issubset(tables)

        assert {column["name"] for column in inspector.get_columns("offshore_period_templates")} == {"id", "tenant_id", "site_id", "name", "description", "duration_days", "start_weekday", "active", "sort_order", "created_at", "updated_at"}
        assert {column["name"] for column in inspector.get_columns("offshore_period_template_events")} == {"id", "tenant_id", "site_id", "period_template_id", "day_offset", "local_time", "service_code", "display_name", "work_position_id", "default_portions", "notes", "sort_order", "active", "created_at", "updated_at"}
        assert {column["name"] for column in inspector.get_columns("offshore_work_periods")} == {"id", "tenant_id", "site_id", "period_template_id", "menu_cycle_id", "name", "starts_at", "ends_at", "status", "notes", "created_at", "updated_at"}
        assert {column["name"] for column in inspector.get_columns("offshore_service_events")} == {"id", "tenant_id", "site_id", "work_period_id", "source_template_event_id", "starts_at", "service_code", "display_name", "work_position_id", "expected_portions", "status", "notes", "created_at", "updated_at"}

        template_uniques = {tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("offshore_period_templates")}
        template_event_uniques = {tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("offshore_period_template_events")}
        service_event_uniques = {tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("offshore_service_events")}

        assert ("tenant_id", "site_id", "name", "active") in template_uniques
        assert ("period_template_id", "day_offset", "local_time", "service_code") in template_event_uniques
        assert ("work_period_id", "source_template_event_id") in service_event_uniques

        period_template_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("offshore_period_templates")}
        period_event_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("offshore_period_template_events")}
        work_period_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("offshore_work_periods")}
        service_event_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("offshore_service_events")}

        assert period_template_fks == {"tenants", "sites"}
        assert period_event_fks == {"tenants", "sites", "offshore_period_templates", "offshore_work_positions"}
        assert work_period_fks == {"tenants", "sites", "offshore_period_templates", "offshore_menu_cycles"}
        assert service_event_fks == {"tenants", "sites", "offshore_work_periods", "offshore_period_template_events", "offshore_work_positions"}

        template_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_period_templates")}
        template_event_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_period_template_events")}
        period_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_work_periods")}
        service_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_service_events")}

        assert "ix_offshore_period_templates_tenant_site_active_sort" in template_indexes
        assert "ix_offshore_period_templates_tenant_site_name" in template_indexes
        assert "ix_offshore_period_template_events_template_sort" in template_event_indexes
        assert "ix_offshore_period_template_events_tenant_site" in template_event_indexes
        assert "ix_offshore_work_periods_tenant_site_starts_at" in period_indexes
        assert "ix_offshore_work_periods_tenant_site_ends_at" in period_indexes
        assert "ix_offshore_work_periods_tenant_site_status" in period_indexes
        assert "ix_offshore_service_events_work_period_starts_at" in service_indexes
        assert "ix_offshore_service_events_tenant_site_status" in service_indexes

        assert any(constraint["name"] == "ck_offshore_period_templates_duration_positive" for constraint in inspector.get_check_constraints("offshore_period_templates"))
        assert any(constraint["name"] == "ck_offshore_period_template_events_day_offset_nonnegative" for constraint in inspector.get_check_constraints("offshore_period_template_events"))
        assert any(constraint["name"] == "ck_offshore_work_periods_starts_before_ends" for constraint in inspector.get_check_constraints("offshore_work_periods"))
        assert any(constraint["name"] == "ck_offshore_service_events_expected_portions_nonnegative" for constraint in inspector.get_check_constraints("offshore_service_events"))

        with engine.begin() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_period_templates")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_period_template_events")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_work_periods")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_service_events")).scalar_one() == 0
    finally:
        engine.dispose()

    _downgrade_to_revision(db_url, "0026_add_offshore_v2_installation_settings")
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "offshore_period_templates" not in tables
        assert "offshore_period_template_events" not in tables
        assert "offshore_work_periods" not in tables
        assert "offshore_service_events" not in tables
    finally:
        engine.dispose()

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(_alembic_cfg(db_url), "0027_add_offshore_v2_periods")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"offshore_period_templates", "offshore_period_template_events", "offshore_work_periods", "offshore_service_events"}.issubset(tables)
    finally:
        engine.dispose()
