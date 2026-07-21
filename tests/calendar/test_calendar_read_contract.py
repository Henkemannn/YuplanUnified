from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.calendar import (
    CalendarFeedService,
    CalendarFeedWarning,
    CalendarItemMetadata,
    CalendarItemRead,
    CalendarUserContext,
    OffshoreCalendarAdapter,
)
from core.db import create_all, get_session
from core.models import Site, Tenant, CommunBuilderPublicationPin
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import (
    OffshoreMenuCycle,
    OffshoreMenuCycleSlot,
    OffshorePeriodTemplate,
    OffshoreServiceEventMenuContext,
    OffshoreWorkPosition,
)
from modules.offshore2.periods import _service as period_service


def _mk_contract_item(**overrides):
    data = {
        "source_module": "offshore",
        "source_type": "service_event",
        "source_id": "123",
        "tenant_id": 1,
        "site_id": "site-1",
        "starts_at": datetime(2026, 7, 21, 8, 0, tzinfo=UTC),
        "ends_at": None,
        "all_day": False,
        "title": "Breakfast",
        "category": "service_event",
        "status": "planned",
        "detail_url": "/offshore/periods/1",
        "editable": False,
        "priority": None,
        "audience": None,
        "visibility": "site",
        "related_entity_type": "work_period",
        "related_entity_id": 1,
        "metadata": CalendarItemMetadata(menu_context_status="resolved"),
    }
    data.update(overrides)
    return CalendarItemRead(**data)


def _mk_app():
    app = __import__("core.app_factory", fromlist=["create_app"]).create_app(
        {"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"}
    )
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


def _seed_site(app, *, tenant_id: int) -> str:
    site_id = str(uuid.uuid4())
    with app.app_context():
        db = get_session()
        try:
            db.add(Site(id=site_id, name="Rig A", tenant_id=tenant_id))
            db.commit()
        finally:
            db.close()
    return site_id


def _seed_publication(app, *, tenant_id: int, site_id: str, day: date) -> None:
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
                    builder_menu_id="builder-menu-1",
                    builder_menu_version=4,
                    source="manual",
                )
            )
            db.commit()
        finally:
            db.close()


def _seed_offshore_period(app, *, tenant_id: int, site_id: str, unresolved: bool = False):
    with app.app_context():
        db = get_session()
        try:
            position = OffshoreWorkPosition(tenant_id=tenant_id, site_id=site_id, code="kokk", name="Kock", position_type="cook")
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

            template = period_service.create_period_template(
                tenant_id=tenant_id,
                site_id=site_id,
                name="Calendar template",
                duration_days=2,
                active=True,
                sort_order=1,
            )
            period_service.add_template_event(
                tenant_id=tenant_id,
                site_id=site_id,
                template_id=template.id,
                day_offset="1" if unresolved else "0",
                local_time=datetime.strptime("08:00", "%H:%M").time(),
                service_code="breakfast",
                display_name="Breakfast",
                work_position_id=position.id,
                default_portions=10,
                active=True,
            )
            generation = period_service.create_work_period_from_template(
                tenant_id=tenant_id,
                site_id=site_id,
                period_template_id=template.id,
                starts_at="2026-07-20T08:00:00",
                menu_cycle_id=cycle.id,
                start_menu_cycle_slot_id=slot.id,
                name="Generated",
            )
            return generation
        finally:
            db.close()


def test_calendar_item_contract_validates_and_serializes_stably():
    item = _mk_contract_item(metadata=CalendarItemMetadata(menu_context_status="unresolved"))
    assert item.identity == ("offshore", "service_event", "123")
    payload = item.to_dict()
    assert payload["starts_at"] == "2026-07-21T08:00:00+00:00"
    assert payload["metadata"] == {"menu_context_status": "unresolved"}

    with pytest.raises(ValueError):
        _mk_contract_item(source_module="")
    with pytest.raises(ValueError):
        _mk_contract_item(starts_at=datetime(2026, 7, 21, 8, 0))
    with pytest.raises(ValueError):
        _mk_contract_item(ends_at=datetime(2026, 7, 21, 7, 0, tzinfo=UTC))
    with pytest.raises(ValueError):
        _mk_contract_item(detail_url="https://example.com")


class _FakeAdapter:
    def __init__(self, name: str, items: list[CalendarItemRead] | None = None, boom: str | None = None):
        self.adapter_name = name
        self._items = items or []
        self._boom = boom

    def get_items(self, *, tenant_id: int, site_id: str | None, range_start: datetime, range_end: datetime, user_context: CalendarUserContext) -> list[CalendarItemRead]:
        if self._boom is not None:
            raise RuntimeError(self._boom)
        return list(self._items)


def test_calendar_feed_service_merges_sorts_dedupes_and_collects_warnings():
    item_one = _mk_contract_item(source_id="1", starts_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC), title="A")
    item_two = _mk_contract_item(source_id="2", starts_at=datetime(2026, 7, 21, 7, 0, tzinfo=UTC), title="B", category="notice")
    item_three = _mk_contract_item(source_module="builder", source_type="publication", source_id="3", starts_at=datetime(2026, 7, 22, 8, 0, tzinfo=UTC), title="C")
    item_three_same_source = _mk_contract_item(source_module="builder", source_type="publication", source_id="1", starts_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC), title="Builder one")
    duplicate_same = _mk_contract_item(source_id="1", starts_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC), title="A")
    duplicate_diff = _mk_contract_item(source_id="1", starts_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC), title="Changed")
    overlap_item = _mk_contract_item(source_id="4", starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=UTC), ends_at=datetime(2026, 7, 21, 1, 0, tzinfo=UTC), title="Overlap")
    outside_item = _mk_contract_item(source_id="5", starts_at=datetime(2026, 7, 20, 1, 0, tzinfo=UTC), ends_at=datetime(2026, 7, 20, 2, 0, tzinfo=UTC), title="Outside")

    service = CalendarFeedService(
        adapters=[
            _FakeAdapter("ok-a", [item_one, item_three, item_three_same_source, duplicate_same, duplicate_diff, overlap_item, outside_item]),
            _FakeAdapter("boom", boom="adapter failed"),
            _FakeAdapter("ok-b", [item_two]),
        ]
    )
    result = service.get_feed(
        tenant_id=1,
        site_id="site-1",
        range_start=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
        range_end=datetime(2026, 7, 23, 0, 0, tzinfo=UTC),
        user_context=CalendarUserContext(tenant_id=1, site_id="site-1", role="viewer"),
    )
    assert [item.identity for item in result.items] == [
        ("offshore", "service_event", "4"),
        ("offshore", "service_event", "2"),
        ("offshore", "service_event", "1"),
        ("builder", "publication", "1"),
        ("builder", "publication", "3"),
    ]
    assert any(warning.adapter_name == "boom" and warning.code == "adapter_error" for warning in result.warnings)
    assert any(warning.code == "duplicate_identity" for warning in result.warnings)
    assert all(item.source_id != "5" for item in result.items)


def test_calendar_feed_service_range_semantics_include_overlap_and_exclude_exact_boundaries():
    service = CalendarFeedService(
        adapters=[
            _FakeAdapter(
                "range",
                [
                    _mk_contract_item(source_id="inside-point", starts_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC), title="Inside point"),
                    _mk_contract_item(source_id="spans-range", starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=UTC), ends_at=datetime(2026, 7, 22, 0, 0, tzinfo=UTC), title="Spans"),
                    _mk_contract_item(source_id="starts-at-end", starts_at=datetime(2026, 7, 23, 0, 0, tzinfo=UTC), title="Ends boundary"),
                    _mk_contract_item(source_id="ends-at-start", starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=UTC), ends_at=datetime(2026, 7, 21, 0, 0, tzinfo=UTC), title="Starts boundary"),
                ],
            )
        ]
    )
    result = service.get_feed(
        tenant_id=1,
        site_id="site-1",
        range_start=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
        range_end=datetime(2026, 7, 23, 0, 0, tzinfo=UTC),
        user_context=CalendarUserContext(tenant_id=1, site_id="site-1", role="viewer"),
    )
    assert [item.source_id for item in result.items] == ["spans-range", "inside-point"]


def test_calendar_feed_service_filters_scope_and_handles_empty_feed():
    valid = _mk_contract_item(source_id="valid", tenant_id=1, site_id="site-1", starts_at=datetime(2026, 7, 21, 1, 0, tzinfo=UTC), title="Valid")
    wrong_tenant = _mk_contract_item(source_id="wrong-tenant", tenant_id=2, site_id="site-1", starts_at=datetime(2026, 7, 21, 2, 0, tzinfo=UTC), title="Wrong tenant")
    wrong_site = _mk_contract_item(source_id="wrong-site", tenant_id=1, site_id="site-2", starts_at=datetime(2026, 7, 21, 3, 0, tzinfo=UTC), title="Wrong site")
    out_of_range = _mk_contract_item(source_id="outside", tenant_id=1, site_id="site-1", starts_at=datetime(2026, 7, 25, 1, 0, tzinfo=UTC), title="Outside")
    service = CalendarFeedService(adapters=[_FakeAdapter("scope", [valid, wrong_tenant, wrong_site, out_of_range])])
    result = service.get_feed(
        tenant_id=1,
        site_id="site-1",
        range_start=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
        range_end=datetime(2026, 7, 23, 0, 0, tzinfo=UTC),
        user_context=CalendarUserContext(tenant_id=1, site_id="site-1", role="viewer"),
    )
    assert [item.source_id for item in result.items] == ["valid"]
    assert CalendarFeedService(adapters=[]).get_feed(
        tenant_id=1,
        site_id="site-1",
        range_start=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
        range_end=datetime(2026, 7, 23, 0, 0, tzinfo=UTC),
        user_context=CalendarUserContext(tenant_id=1, site_id="site-1", role="viewer"),
    ).items == []


def test_offshore_adapter_emits_items_and_respects_permissions_and_scope():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20))
    generation = _seed_offshore_period(app, tenant_id=1, site_id=site_id, unresolved=True)

    adapter = OffshoreCalendarAdapter()
    range_start = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 7, 23, 0, 0, tzinfo=UTC)

    with app.app_context():
        viewer_items = adapter.get_items(
            tenant_id=1,
            site_id=site_id,
            range_start=range_start,
            range_end=range_end,
            user_context=CalendarUserContext(tenant_id=1, site_id=site_id, user_id=7, role="viewer"),
        )
        assert len(viewer_items) == 1
        item = viewer_items[0]
        assert item.source_module == "offshore"
        assert item.source_type == "service_event"
        assert item.source_id.isdigit()
        assert item.tenant_id == 1
        assert item.site_id == site_id
        assert item.starts_at.tzinfo is not None and item.starts_at.utcoffset() is not None
        assert item.title == "Breakfast"
        assert item.category == "service_event"
        assert item.status in {"planned", "active", "completed", "cancelled", "confirmed"}
        assert item.detail_url == f"/offshore/periods/{generation.work_period.id}"
        assert item.editable is False
        assert item.related_entity_type == "work_period"
        assert item.related_entity_id == generation.work_period.id
        assert item.visibility == "site"
        assert item.metadata is not None
        assert item.metadata.menu_context_status in {"resolved", "unresolved"}

        editor_items = adapter.get_items(
            tenant_id=1,
            site_id=site_id,
            range_start=range_start,
            range_end=range_end,
            user_context=CalendarUserContext(tenant_id=1, site_id=site_id, user_id=7, role="editor"),
        )
        assert editor_items and editor_items[0].editable is True

        other_site_items = adapter.get_items(
            tenant_id=1,
            site_id=str(uuid.uuid4()),
            range_start=range_start,
            range_end=range_end,
            user_context=CalendarUserContext(tenant_id=1, site_id=site_id, user_id=7, role="viewer"),
        )
        assert other_site_items == []

        with app.app_context():
            db = get_session()
            try:
                db.execute(text("DELETE FROM offshore_service_event_menu_contexts WHERE tenant_id=:t AND site_id=:s"), {"t": 1, "s": site_id})
                db.commit()
            finally:
                db.close()

        missing_context_items = adapter.get_items(
            tenant_id=1,
            site_id=site_id,
            range_start=range_start,
            range_end=range_end,
            user_context=CalendarUserContext(tenant_id=1, site_id=site_id, user_id=7, role="viewer"),
        )
        assert len(missing_context_items) == 1
        assert missing_context_items[0].metadata is not None
        assert missing_context_items[0].metadata.menu_context_status is None


def test_offshore_adapter_emits_canonical_utc_and_writes_nothing():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1)
    _seed_publication(app, tenant_id=1, site_id=site_id, day=date(2026, 7, 20))
    _seed_offshore_period(app, tenant_id=1, site_id=site_id, unresolved=False)

    adapter = OffshoreCalendarAdapter()
    range_start = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 7, 23, 0, 0, tzinfo=UTC)

    with app.app_context():
        db = get_session()
        try:
            before_event_count = db.query(OffshoreServiceEventMenuContext).count()
            before_slot_count = db.query(OffshoreMenuCycleSlot).count()
        finally:
            db.close()

        items = adapter.get_items(
            tenant_id=1,
            site_id=site_id,
            range_start=range_start,
            range_end=range_end,
            user_context=CalendarUserContext(tenant_id=1, site_id=site_id, user_id=7, role="cook"),
        )
        assert items and items[0].editable is False
        assert items[0].starts_at.tzinfo is UTC
        assert items[0].starts_at.isoformat().endswith("+00:00")

        db = get_session()
        try:
            after_event_count = db.query(OffshoreServiceEventMenuContext).count()
            after_slot_count = db.query(OffshoreMenuCycleSlot).count()
        finally:
            db.close()

    assert before_event_count == after_event_count
    assert before_slot_count == after_slot_count


def test_calendar_no_persistence_schema_or_migration():
    from core.models import Base

    assert not any("calendar" in name.lower() for name in Base.metadata.tables)
    migration_dir = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    assert not any("calendar" in path.name.lower() for path in migration_dir.glob("*.py"))
