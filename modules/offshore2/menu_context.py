from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.db import get_new_session, get_session

from .models import (
    OffshoreMenuCycle,
    OffshoreMenuCycleSlot,
    OffshoreServiceEvent,
    OffshoreServiceEventMenuContext,
    OffshoreWorkPeriod,
)


CONTEXT_RESOLUTION_STATUSES = ("resolved", "unresolved", "unavailable", "manual")
CONTEXT_ASSIGNMENT_SOURCES = ("automatic", "manual")
CONTEXT_MATCH_STATUSES = ("matched", "missing", "ambiguous", "withdrawn")


@dataclass(frozen=True)
class OffshoreMenuContextResolution:
    service_date: date
    menu_cycle_id: int | None
    start_menu_cycle_slot_id: int | None
    menu_cycle_slot_id: int | None
    menu_cycle_index: int | None
    service_key: str | None
    resolution_status: str
    assignment_source: str
    match_status: str | None
    resolution_reason: str | None
    manual_note: str | None
    builder_publication_pin_id: str | None
    builder_publication_year: int
    builder_publication_week: int
    builder_menu_id: str | None
    builder_menu_version: int | None


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _normalize_service_key(value: object | None) -> str | None:
    raw = _clean(value).lower()
    return raw or None


def _site_tenant_id(db, site_id: str) -> int | None:
    if not site_id:
        return None
    row = db.execute(text("SELECT tenant_id FROM sites WHERE id = :sid"), {"sid": site_id}).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _validate_scope(db, tenant_id: int | None, site_id: str | None) -> None:
    if tenant_id is None or not site_id:
        raise ValueError("offshore.validation.missing_context")
    site_tenant_id = _site_tenant_id(db, site_id)
    if site_tenant_id is None or int(site_tenant_id) != int(tenant_id):
        raise LookupError("offshore.validation.cross_site")


def _validate_timezone_name(timezone_name: str | None) -> str:
    candidate = _clean(timezone_name) or "Europe/Oslo"
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("offshore.validation.invalid_timezone") from exc
    return candidate


def _site_timezone_name(db, tenant_id: int | None, site_id: str | None) -> str:
    if tenant_id is None or not site_id:
        return "Europe/Oslo"
    row = db.execute(
        text("SELECT timezone FROM offshore_installation_settings WHERE tenant_id = :tenant_id AND site_id = :site_id"),
        {"tenant_id": int(tenant_id), "site_id": str(site_id)},
    ).fetchone()
    if row and row[0]:
        return _validate_timezone_name(str(row[0]))
    return "Europe/Oslo"


def _local_zone(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(_validate_timezone_name(timezone_name))


def _service_date(value: datetime, timezone_name: str) -> date:
    return value.astimezone(_local_zone(timezone_name)).date()


def _iso_year_week(value: date) -> tuple[int, int]:
    iso_calendar = value.isocalendar()
    return int(iso_calendar.year), int(iso_calendar.week)


class OffshoreMenuContextService:
    def __init__(self, *, publication_repository: CommunBuilderPublicationRepository | None = None) -> None:
        self._publication_repository = publication_repository or CommunBuilderPublicationRepository()

    def _base_query(self, db, model, tenant_id: int, site_id: str):
        return db.query(model).filter(model.tenant_id == int(tenant_id), model.site_id == str(site_id))

    def _get_work_period(self, db, tenant_id: int, site_id: str, work_period_id: int) -> OffshoreWorkPeriod | None:
        return self._base_query(db, OffshoreWorkPeriod, tenant_id, site_id).filter(OffshoreWorkPeriod.id == int(work_period_id)).first()

    def _get_service_event(self, db, tenant_id: int, site_id: str, service_event_id: int) -> OffshoreServiceEvent | None:
        return self._base_query(db, OffshoreServiceEvent, tenant_id, site_id).filter(OffshoreServiceEvent.id == int(service_event_id)).first()

    def _get_menu_cycle_slot(self, db, tenant_id: int, site_id: str, menu_cycle_id: int | None, menu_cycle_index: int | None) -> OffshoreMenuCycleSlot | None:
        if menu_cycle_id is None or menu_cycle_index is None:
            return None
        return (
            self._base_query(db, OffshoreMenuCycleSlot, tenant_id, site_id)
            .filter(
                OffshoreMenuCycleSlot.menu_cycle_id == int(menu_cycle_id),
                OffshoreMenuCycleSlot.cycle_index == int(menu_cycle_index),
            )
            .first()
        )

    def _get_start_slot(self, db, tenant_id: int, site_id: str, period: OffshoreWorkPeriod) -> OffshoreMenuCycleSlot | None:
        if period.start_menu_cycle_slot_id is not None:
            slot = self._base_query(db, OffshoreMenuCycleSlot, tenant_id, site_id).filter(OffshoreMenuCycleSlot.id == int(period.start_menu_cycle_slot_id)).first()
            if slot is not None:
                return slot
        if period.menu_cycle_id is None:
            return None
        return (
            self._base_query(db, OffshoreMenuCycleSlot, tenant_id, site_id)
            .filter(OffshoreMenuCycleSlot.menu_cycle_id == int(period.menu_cycle_id), OffshoreMenuCycleSlot.is_active.is_(True))
            .order_by(OffshoreMenuCycleSlot.cycle_index.asc(), OffshoreMenuCycleSlot.sort_order.asc(), OffshoreMenuCycleSlot.id.asc())
            .first()
        )

    def _resolve_cycle_slot(self, db, tenant_id: int, site_id: str, period: OffshoreWorkPeriod, event: OffshoreServiceEvent, timezone_name: str) -> tuple[int | None, int | None, int | None]:
        if period.menu_cycle_id is None:
            return None, None, None
        menu_cycle = self._base_query(db, OffshoreMenuCycle, tenant_id, site_id).filter(OffshoreMenuCycle.id == int(period.menu_cycle_id)).first()
        start_slot = self._get_start_slot(db, tenant_id, site_id, period)
        if menu_cycle is None or int(menu_cycle.cycle_length) < 1 or start_slot is None:
            return int(period.menu_cycle_id), None, int(start_slot.id) if start_slot is not None else None
        start_day = period.starts_at.astimezone(_local_zone(timezone_name)).date()
        event_day = event.starts_at.astimezone(_local_zone(timezone_name)).date()
        day_offset = (event_day - start_day).days
        if day_offset < 0:
            return int(period.menu_cycle_id), None, int(start_slot.id)
        cycle_index = ((int(start_slot.cycle_index) - 1 + day_offset) % int(menu_cycle.cycle_length)) + 1
        slot = self._get_menu_cycle_slot(db, tenant_id, site_id, int(period.menu_cycle_id), cycle_index)
        return int(period.menu_cycle_id), int(slot.id) if slot is not None else None, int(start_slot.id)

    def _resolve_publication(self, *, tenant_id: int, site_id: str, service_date_value: date, db) -> tuple[str | None, int | None, int, int, str, str | None]:
        year, week = _iso_year_week(service_date_value)
        pin = self._publication_repository.get_publication_for_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week, db=db)
        if pin is None:
            return None, None, year, week, "unavailable", "publication_missing"
        return str(pin.id), int(pin.builder_menu_version), year, week, "resolved", None

    def resolve_context(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, service_event_id: int, db=None) -> OffshoreMenuContextResolution:
        owns_session = db is None
        db = db or get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            period = self._get_work_period(db, int(tenant_id), str(site_id), int(work_period_id))
            if period is None:
                raise LookupError("offshore.validation.cross_site")
            event = self._get_service_event(db, int(tenant_id), str(site_id), int(service_event_id))
            if event is None or int(event.work_period_id) != int(work_period_id):
                raise LookupError("offshore.validation.cross_site")

            timezone_name = _site_timezone_name(db, tenant_id, site_id)
            service_date_value = _service_date(event.starts_at, timezone_name)
            menu_cycle_id, menu_cycle_slot_id, start_menu_cycle_slot_id = self._resolve_cycle_slot(db, int(tenant_id), str(site_id), period, event, timezone_name)
            menu_cycle_index = None
            if menu_cycle_slot_id is not None:
                slot = self._base_query(db, OffshoreMenuCycleSlot, int(tenant_id), str(site_id)).filter(OffshoreMenuCycleSlot.id == int(menu_cycle_slot_id)).first()
                menu_cycle_index = int(slot.cycle_index) if slot is not None else None
            service_key = _normalize_service_key(event.service_code)
            builder_publication_pin_id, builder_menu_version, publication_year, publication_week, resolution_status, resolution_reason = self._resolve_publication(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                service_date_value=service_date_value,
                db=db,
            )
            builder_menu_id = None
            if builder_publication_pin_id is not None:
                pin = self._publication_repository.get_publication_for_week(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    year=publication_year,
                    week=publication_week,
                    db=db,
                )
                if pin is not None:
                    builder_menu_id = str(pin.builder_menu_id)
                    builder_menu_version = int(pin.builder_menu_version)
            match_status = "matched" if builder_publication_pin_id is not None else "missing"
            return OffshoreMenuContextResolution(
                service_date=service_date_value,
                menu_cycle_id=menu_cycle_id,
                start_menu_cycle_slot_id=start_menu_cycle_slot_id,
                menu_cycle_slot_id=menu_cycle_slot_id,
                menu_cycle_index=menu_cycle_index,
                service_key=service_key,
                resolution_status=resolution_status,
                assignment_source="automatic",
                match_status=match_status,
                resolution_reason=resolution_reason,
                manual_note=None,
                builder_publication_pin_id=builder_publication_pin_id,
                builder_publication_year=publication_year,
                builder_publication_week=publication_week,
                builder_menu_id=builder_menu_id,
                builder_menu_version=builder_menu_version,
            )
        finally:
            if owns_session:
                db.close()

    def sync_service_event_context(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        work_period_id: int,
        service_event_id: int,
        db=None,
        force: bool = False,
        source: str = "automatic",
        manual_note: str | None = None,
    ) -> OffshoreServiceEventMenuContext:
        owns_session = db is None
        db = db or get_new_session()
        try:
            source_value = str(source or "automatic").strip().lower()
            if source_value not in CONTEXT_ASSIGNMENT_SOURCES:
                raise ValueError("offshore.validation.invalid_context_source")

            resolution = self.resolve_context(
                tenant_id=tenant_id,
                site_id=site_id,
                work_period_id=work_period_id,
                service_event_id=service_event_id,
                db=db,
            )
            period = self._get_work_period(db, int(tenant_id), str(site_id), int(work_period_id))
            if period is None:
                raise LookupError("offshore.validation.cross_site")
            existing = self._base_query(db, OffshoreServiceEventMenuContext, int(tenant_id), str(site_id)).filter(OffshoreServiceEventMenuContext.service_event_id == int(service_event_id)).first()
            if existing is not None and existing.assignment_source == "manual" and source_value == "automatic" and not force:
                return existing
            if existing is not None and period.status == "completed" and source_value == "automatic" and not force:
                return existing

            resolution_status = resolution.resolution_status
            assignment_source = source_value
            match_status = resolution.match_status
            resolution_reason = resolution.resolution_reason
            if source_value == "manual":
                resolution_status = "manual"
                assignment_source = "manual"
                match_status = match_status or "matched"
                resolution_reason = manual_note or resolution_reason or "manual assignment"
            elif resolution.builder_publication_pin_id is None:
                resolution_status = "unavailable"
                assignment_source = "automatic"
            elif resolution.menu_cycle_slot_id is None:
                resolution_status = "unresolved"
                match_status = match_status or "ambiguous"
                resolution_reason = resolution_reason or "menu cycle slot missing"

            if existing is None:
                row = OffshoreServiceEventMenuContext(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    work_period_id=int(work_period_id),
                    service_event_id=int(service_event_id),
                    service_date=resolution.service_date,
                    menu_cycle_id=resolution.menu_cycle_id,
                    start_menu_cycle_slot_id=resolution.start_menu_cycle_slot_id,
                    menu_cycle_slot_id=resolution.menu_cycle_slot_id,
                    menu_cycle_index=resolution.menu_cycle_index,
                    service_key=resolution.service_key,
                    resolution_status=resolution_status,
                    assignment_source=assignment_source,
                    match_status=match_status,
                    resolution_reason=resolution_reason,
                    manual_note=manual_note if source_value == "manual" else None,
                    builder_publication_pin_id=resolution.builder_publication_pin_id,
                    builder_publication_year=resolution.builder_publication_year,
                    builder_publication_week=resolution.builder_publication_week,
                    builder_menu_id=resolution.builder_menu_id,
                    builder_menu_version=resolution.builder_menu_version,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(row)
            else:
                existing.work_period_id = int(work_period_id)
                existing.service_date = resolution.service_date
                existing.menu_cycle_id = resolution.menu_cycle_id
                existing.start_menu_cycle_slot_id = resolution.start_menu_cycle_slot_id
                existing.menu_cycle_slot_id = resolution.menu_cycle_slot_id
                existing.menu_cycle_index = resolution.menu_cycle_index
                existing.service_key = resolution.service_key
                existing.resolution_status = resolution_status
                existing.assignment_source = assignment_source
                existing.match_status = match_status
                existing.resolution_reason = resolution_reason
                if source_value == "manual":
                    existing.manual_note = manual_note
                elif force or existing.assignment_source != "manual":
                    existing.manual_note = None
                existing.builder_publication_pin_id = resolution.builder_publication_pin_id
                existing.builder_publication_year = resolution.builder_publication_year
                existing.builder_publication_week = resolution.builder_publication_week
                existing.builder_menu_id = resolution.builder_menu_id
                existing.builder_menu_version = resolution.builder_menu_version
                existing.updated_at = datetime.now(UTC)
                row = existing

            db.flush()
            if owns_session:
                db.commit()
            db.refresh(row)
            return row
        except Exception:
            if owns_session:
                db.rollback()
            raise
        finally:
            if owns_session:
                db.close()

    def clear_manual_assignment(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, service_event_id: int, db=None) -> OffshoreServiceEventMenuContext:
        return self.sync_service_event_context(
            tenant_id=tenant_id,
            site_id=site_id,
            work_period_id=work_period_id,
            service_event_id=service_event_id,
            db=db,
            force=True,
            source="automatic",
            manual_note=None,
        )

    def get_context_for_event(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, service_event_id: int):
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            row = (
                self._base_query(db, OffshoreServiceEventMenuContext, int(tenant_id), str(site_id))
                .filter(
                    OffshoreServiceEventMenuContext.work_period_id == int(work_period_id),
                    OffshoreServiceEventMenuContext.service_event_id == int(service_event_id),
                )
                .first()
            )
            return row
        finally:
            db.close()

    def list_contexts_for_period(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int):
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshoreServiceEventMenuContext, int(tenant_id), str(site_id))
                .filter(OffshoreServiceEventMenuContext.work_period_id == int(work_period_id))
                .order_by(OffshoreServiceEventMenuContext.service_date.asc(), OffshoreServiceEventMenuContext.service_event_id.asc())
                .all()
            )
        finally:
            db.close()


_service = OffshoreMenuContextService()