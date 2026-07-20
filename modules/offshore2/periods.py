from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime, time as _time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.db import get_new_session, get_session

from .i18n import copy_for, t
from .models import (
    OffshoreInstallationSettings,
    OffshoreMenuCycle,
    OffshorePeriodTemplate,
    OffshorePeriodTemplateEvent,
    OffshoreServiceEvent,
    OffshoreWorkPeriod,
    OffshoreWorkPosition,
)


PERIOD_TEMPLATE_EVENT_STATUSES = ("planned", "confirmed", "completed", "cancelled")
WORK_PERIOD_STATUSES = ("draft", "planned", "active", "completed", "cancelled")


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(value: object | None) -> str:
    return str(value or "").strip()


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


def _validate_name(value: object | None, key: str = "offshore.validation.name_required") -> str:
    name = _clean(value)
    if not name:
        raise ValueError(key)
    return name


def _validate_day_offset(value: object | None, duration_days: int) -> int:
    raw = _clean(value)
    try:
        offset = int(raw)
    except Exception as exc:
        raise ValueError("offshore.validation.invalid_day_offset") from exc
    if offset < 0 or offset >= int(duration_days):
        raise ValueError("offshore.validation.invalid_day_offset")
    return offset


def _validate_sort_order(value: object | None) -> int:
    raw = _clean(value)
    if not raw:
        return 0
    try:
        order = int(raw)
    except Exception as exc:
        raise ValueError("offshore.validation.invalid_sort_order") from exc
    if order < 0:
        raise ValueError("offshore.validation.invalid_sort_order")
    return order


def _validate_portions(value: object | None) -> int | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        portions = int(raw)
    except Exception as exc:
        raise ValueError("offshore.validation.invalid_portions") from exc
    if portions < 0:
        raise ValueError("offshore.validation.invalid_portions")
    return portions


def _validate_status(value: object | None, allowed: tuple[str, ...], key: str) -> str:
    status = _clean(value).lower()
    if status not in allowed:
        raise ValueError(key)
    return status


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
    row = (
        db.query(OffshoreInstallationSettings.timezone)
        .filter(OffshoreInstallationSettings.tenant_id == int(tenant_id), OffshoreInstallationSettings.site_id == str(site_id))
        .first()
    )
    if row and row[0]:
        return _validate_timezone_name(str(row[0]))
    return "Europe/Oslo"


def site_timezone_name(tenant_id: int | None, site_id: str | None) -> str:
    db = get_session()
    try:
        _validate_scope(db, tenant_id, site_id)
        return _site_timezone_name(db, tenant_id, site_id)
    finally:
        db.close()


def _local_zone(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(_validate_timezone_name(timezone_name))


def _ensure_local_datetime(value: datetime | str | None, timezone_name: str) -> datetime:
    zone = _local_zone(timezone_name)
    if value is None:
        raise ValueError("offshore.validation.invalid_starts_at")
    if isinstance(value, str):
        candidate = datetime.fromisoformat(value)
    else:
        candidate = value
    if candidate.tzinfo is None:
        return candidate.replace(tzinfo=zone)
    return candidate.astimezone(zone)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_date_label(value: datetime, timezone_name: str) -> str:
    local_dt = value.astimezone(_local_zone(timezone_name))
    return local_dt.strftime("%Y-%m-%d %H:%M")


def _weekday_name(locale: str, weekday: int) -> str:
    return t(locale, f"offshore.weekday.{int(weekday) % 7}")


@dataclass(frozen=True)
class OffshorePeriodGeneration:
    work_period: OffshoreWorkPeriod
    service_events: list[OffshoreServiceEvent]


class OffshorePeriodService:
    def _base_query(self, db, model, tenant_id: int, site_id: str):
        return db.query(model).filter(model.tenant_id == int(tenant_id), model.site_id == str(site_id))

    def _ensure_work_position_scope(self, db, tenant_id: int, site_id: str, work_position_id: int | None) -> None:
        if work_position_id is None:
            return
        row = self._base_query(db, OffshoreWorkPosition, tenant_id, site_id).filter(OffshoreWorkPosition.id == int(work_position_id)).first()
        if row is None:
            raise LookupError("offshore.validation.cross_site")

    def _ensure_menu_cycle_scope(self, db, tenant_id: int, site_id: str, menu_cycle_id: int | None) -> None:
        if menu_cycle_id is None:
            return
        row = self._base_query(db, OffshoreMenuCycle, tenant_id, site_id).filter(OffshoreMenuCycle.id == int(menu_cycle_id)).first()
        if row is None:
            raise LookupError("offshore.validation.cross_site")

    def _get_template(self, db, tenant_id: int, site_id: str, template_id: int) -> OffshorePeriodTemplate | None:
        return self._base_query(db, OffshorePeriodTemplate, tenant_id, site_id).filter(OffshorePeriodTemplate.id == int(template_id)).first()

    def _get_template_event(self, db, tenant_id: int, site_id: str, event_id: int) -> OffshorePeriodTemplateEvent | None:
        return self._base_query(db, OffshorePeriodTemplateEvent, tenant_id, site_id).filter(OffshorePeriodTemplateEvent.id == int(event_id)).first()

    def _get_period(self, db, tenant_id: int, site_id: str, period_id: int) -> OffshoreWorkPeriod | None:
        return self._base_query(db, OffshoreWorkPeriod, tenant_id, site_id).filter(OffshoreWorkPeriod.id == int(period_id)).first()

    def _get_service_event(self, db, tenant_id: int, site_id: str, event_id: int) -> OffshoreServiceEvent | None:
        return self._base_query(db, OffshoreServiceEvent, tenant_id, site_id).filter(OffshoreServiceEvent.id == int(event_id)).first()

    def _active_template_events(self, db, template_id: int) -> list[OffshorePeriodTemplateEvent]:
        return (
            db.query(OffshorePeriodTemplateEvent)
            .filter(OffshorePeriodTemplateEvent.period_template_id == int(template_id), OffshorePeriodTemplateEvent.active.is_(True))
            .order_by(
                OffshorePeriodTemplateEvent.day_offset.asc(),
                OffshorePeriodTemplateEvent.local_time.asc(),
                OffshorePeriodTemplateEvent.sort_order.asc(),
                OffshorePeriodTemplateEvent.id.asc(),
            )
            .all()
        )

    def list_work_positions(self, tenant_id: int | None, site_id: str | None) -> list[OffshoreWorkPosition]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshoreWorkPosition, int(tenant_id), str(site_id))
                .order_by(OffshoreWorkPosition.sort_order.asc(), OffshoreWorkPosition.id.asc())
                .all()
            )
        finally:
            db.close()

    def list_menu_cycles(self, tenant_id: int | None, site_id: str | None) -> list[OffshoreMenuCycle]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshoreMenuCycle, int(tenant_id), str(site_id))
                .order_by(OffshoreMenuCycle.is_active.desc(), OffshoreMenuCycle.name.asc(), OffshoreMenuCycle.id.asc())
                .all()
            )
        finally:
            db.close()

    def list_period_templates(self, tenant_id: int | None, site_id: str | None) -> list[OffshorePeriodTemplate]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshorePeriodTemplate, int(tenant_id), str(site_id))
                .order_by(OffshorePeriodTemplate.active.desc(), OffshorePeriodTemplate.sort_order.asc(), OffshorePeriodTemplate.name.asc(), OffshorePeriodTemplate.id.asc())
                .all()
            )
        finally:
            db.close()

    def get_period_template(self, tenant_id: int | None, site_id: str | None, template_id: int) -> OffshorePeriodTemplate | None:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return self._get_template(db, int(tenant_id), str(site_id), int(template_id))
        finally:
            db.close()

    def create_period_template(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        name: str,
        duration_days: int,
        description: str | None = None,
        start_weekday: int | None = None,
        active: bool = True,
        sort_order: int | None = None,
    ) -> OffshorePeriodTemplate:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            template_name = _validate_name(name)
            if int(duration_days) < 1:
                raise ValueError("offshore.validation.invalid_duration_days")
            if start_weekday is not None and (int(start_weekday) < 0 or int(start_weekday) > 6):
                raise ValueError("offshore.validation.invalid_start_weekday")
            existing = (
                self._base_query(db, OffshorePeriodTemplate, int(tenant_id), str(site_id))
                .filter(OffshorePeriodTemplate.name == template_name, OffshorePeriodTemplate.active.is_(True))
                .first()
            )
            if existing is not None and active:
                raise ValueError("offshore.validation.duplicate_template_name")
            next_sort = sort_order
            if next_sort is None:
                max_sort = db.query(OffshorePeriodTemplate.sort_order).filter_by(tenant_id=int(tenant_id), site_id=str(site_id)).order_by(OffshorePeriodTemplate.sort_order.desc()).first()
                next_sort = int(max_sort[0]) + 1 if max_sort and max_sort[0] is not None else 1
            row = OffshorePeriodTemplate(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                name=template_name,
                description=_clean(description) or None,
                duration_days=int(duration_days),
                start_weekday=int(start_weekday) if start_weekday is not None else None,
                active=bool(active),
                sort_order=int(next_sort),
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_period_template(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        template_id: int,
        name: str,
        duration_days: int,
        description: str | None = None,
        start_weekday: int | None = None,
        active: bool = True,
        sort_order: int | None = None,
    ) -> OffshorePeriodTemplate:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            row = self._get_template(db, int(tenant_id), str(site_id), int(template_id))
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            template_name = _validate_name(name)
            if int(duration_days) < 1:
                raise ValueError("offshore.validation.invalid_duration_days")
            if start_weekday is not None and (int(start_weekday) < 0 or int(start_weekday) > 6):
                raise ValueError("offshore.validation.invalid_start_weekday")
            duplicate = (
                self._base_query(db, OffshorePeriodTemplate, int(tenant_id), str(site_id))
                .filter(
                    OffshorePeriodTemplate.id != int(template_id),
                    OffshorePeriodTemplate.name == template_name,
                    OffshorePeriodTemplate.active.is_(True),
                )
                .first()
            )
            if duplicate is not None and active:
                raise ValueError("offshore.validation.duplicate_template_name")
            row.name = template_name
            row.description = _clean(description) or None
            row.duration_days = int(duration_days)
            row.start_weekday = int(start_weekday) if start_weekday is not None else None
            row.active = bool(active)
            if sort_order is not None:
                row.sort_order = int(sort_order)
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def archive_period_template(self, *, tenant_id: int | None, site_id: str | None, template_id: int) -> OffshorePeriodTemplate:
        return self.update_period_template(
            tenant_id=tenant_id,
            site_id=site_id,
            template_id=template_id,
            name=self.get_period_template(tenant_id, site_id, template_id).name,  # type: ignore[union-attr]
            duration_days=self.get_period_template(tenant_id, site_id, template_id).duration_days,  # type: ignore[union-attr]
            description=self.get_period_template(tenant_id, site_id, template_id).description,  # type: ignore[union-attr]
            start_weekday=self.get_period_template(tenant_id, site_id, template_id).start_weekday,  # type: ignore[union-attr]
            active=False,
            sort_order=self.get_period_template(tenant_id, site_id, template_id).sort_order,  # type: ignore[union-attr]
        )

    def list_template_events(self, tenant_id: int | None, site_id: str | None, template_id: int) -> list[OffshorePeriodTemplateEvent]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return self._active_template_events(db, int(template_id))
        finally:
            db.close()

    def add_template_event(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        template_id: int,
        day_offset: int,
        local_time: _time,
        service_code: str,
        display_name: str,
        work_position_id: int | None = None,
        default_portions: int | None = None,
        notes: str | None = None,
        sort_order: int | None = None,
        active: bool = True,
    ) -> OffshorePeriodTemplateEvent:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            template = self._get_template(db, int(tenant_id), str(site_id), int(template_id))
            if template is None:
                raise LookupError("offshore.validation.cross_site")
            offset = _validate_day_offset(day_offset, int(template.duration_days))
            self._ensure_work_position_scope(db, int(tenant_id), str(site_id), work_position_id)
            code = _validate_name(service_code, key="offshore.validation.service_code_required")
            name = _validate_name(display_name)
            if default_portions is not None and int(default_portions) < 0:
                raise ValueError("offshore.validation.invalid_portions")
            duplicate = (
                self._base_query(db, OffshorePeriodTemplateEvent, int(tenant_id), str(site_id))
                .filter(
                    OffshorePeriodTemplateEvent.period_template_id == int(template_id),
                    OffshorePeriodTemplateEvent.day_offset == int(offset),
                    OffshorePeriodTemplateEvent.local_time == local_time,
                    OffshorePeriodTemplateEvent.service_code == code,
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError("offshore.validation.duplicate_template_event")
            next_sort = sort_order
            if next_sort is None:
                max_sort = db.query(OffshorePeriodTemplateEvent.sort_order).filter_by(period_template_id=int(template_id)).order_by(OffshorePeriodTemplateEvent.sort_order.desc()).first()
                next_sort = int(max_sort[0]) + 1 if max_sort and max_sort[0] is not None else 1
            row = OffshorePeriodTemplateEvent(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                period_template_id=int(template_id),
                day_offset=int(offset),
                local_time=local_time,
                service_code=code,
                display_name=name,
                work_position_id=int(work_position_id) if work_position_id is not None else None,
                default_portions=int(default_portions) if default_portions is not None else None,
                notes=_clean(notes) or None,
                sort_order=int(next_sort),
                active=bool(active),
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_template_event(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        template_id: int,
        event_id: int,
        payload: dict[str, object],
    ) -> OffshorePeriodTemplateEvent:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            template = self._get_template(db, int(tenant_id), str(site_id), int(template_id))
            if template is None:
                raise LookupError("offshore.validation.cross_site")
            row = self._get_template_event(db, int(tenant_id), str(site_id), int(event_id))
            if row is None or int(row.period_template_id) != int(template_id):
                raise LookupError("offshore.validation.cross_site")
            new_day_offset = _validate_day_offset(payload.get("day_offset", row.day_offset), int(template.duration_days))
            new_local_time = payload.get("local_time") or row.local_time
            if isinstance(new_local_time, str):
                new_local_time = datetime.strptime(new_local_time, "%H:%M").time()
            self._ensure_work_position_scope(db, int(tenant_id), str(site_id), payload.get("work_position_id") if payload.get("work_position_id") is not None else row.work_position_id)
            new_service_code = _validate_name(payload.get("service_code", row.service_code), key="offshore.validation.service_code_required")
            new_display_name = _validate_name(payload.get("display_name", row.display_name))
            new_work_position_id = payload.get("work_position_id")
            new_default_portions = _validate_portions(payload.get("default_portions")) if "default_portions" in payload else row.default_portions
            new_notes = _clean(payload.get("notes")) if "notes" in payload else row.notes
            new_active = bool(payload.get("active", row.active))
            new_sort_order = _validate_sort_order(payload.get("sort_order")) if "sort_order" in payload else row.sort_order
            duplicate = (
                self._base_query(db, OffshorePeriodTemplateEvent, int(tenant_id), str(site_id))
                .filter(
                    OffshorePeriodTemplateEvent.id != int(event_id),
                    OffshorePeriodTemplateEvent.period_template_id == int(template_id),
                    OffshorePeriodTemplateEvent.day_offset == int(new_day_offset),
                    OffshorePeriodTemplateEvent.local_time == new_local_time,
                    OffshorePeriodTemplateEvent.service_code == new_service_code,
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError("offshore.validation.duplicate_template_event")
            row.day_offset = int(new_day_offset)
            row.local_time = new_local_time
            row.service_code = new_service_code
            row.display_name = new_display_name
            row.work_position_id = int(new_work_position_id) if new_work_position_id is not None else None
            row.default_portions = int(new_default_portions) if new_default_portions is not None else None
            row.notes = new_notes or None
            row.sort_order = int(new_sort_order)
            row.active = bool(new_active)
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_template_event(self, *, tenant_id: int | None, site_id: str | None, template_id: int, event_id: int) -> None:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            row = self._get_template_event(db, int(tenant_id), str(site_id), int(event_id))
            if row is None or int(row.period_template_id) != int(template_id):
                raise LookupError("offshore.validation.cross_site")
            db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_work_periods(self, tenant_id: int | None, site_id: str | None) -> list[OffshoreWorkPeriod]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshoreWorkPeriod, int(tenant_id), str(site_id))
                .order_by(OffshoreWorkPeriod.starts_at.desc(), OffshoreWorkPeriod.id.desc())
                .all()
            )
        finally:
            db.close()

    def get_work_period(self, tenant_id: int | None, site_id: str | None, period_id: int) -> OffshoreWorkPeriod | None:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return self._get_period(db, int(tenant_id), str(site_id), int(period_id))
        finally:
            db.close()

    def create_work_period(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        name: str,
        starts_at: datetime | str,
        ends_at: datetime | str,
        period_template_id: int | None = None,
        menu_cycle_id: int | None = None,
        status: str = "planned",
        notes: str | None = None,
    ) -> OffshoreWorkPeriod:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            if period_template_id is not None:
                template = self._get_template(db, int(tenant_id), str(site_id), int(period_template_id))
                if template is None:
                    raise LookupError("offshore.validation.cross_site")
            self._ensure_menu_cycle_scope(db, int(tenant_id), str(site_id), menu_cycle_id)
            starts_local = _ensure_local_datetime(starts_at, _site_timezone_name(db, tenant_id, site_id))
            ends_local = _ensure_local_datetime(ends_at, _site_timezone_name(db, tenant_id, site_id))
            if _utc_datetime(starts_local) >= _utc_datetime(ends_local):
                raise ValueError("offshore.validation.invalid_period_range")
            row = OffshoreWorkPeriod(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                period_template_id=int(period_template_id) if period_template_id is not None else None,
                menu_cycle_id=int(menu_cycle_id) if menu_cycle_id is not None else None,
                name=_validate_name(name),
                starts_at=_utc_datetime(starts_local),
                ends_at=_utc_datetime(ends_local),
                status=_validate_status(status, WORK_PERIOD_STATUSES, "offshore.validation.invalid_period_status"),
                notes=_clean(notes) or None,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_work_period(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        period_id: int,
        payload: dict[str, object],
    ) -> OffshoreWorkPeriod:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            row = self._get_period(db, int(tenant_id), str(site_id), int(period_id))
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            if "name" in payload:
                row.name = _validate_name(payload.get("name"))
            if "starts_at" in payload:
                row.starts_at = _utc_datetime(_ensure_local_datetime(payload.get("starts_at"), _site_timezone_name(db, tenant_id, site_id)))
            if "ends_at" in payload:
                row.ends_at = _utc_datetime(_ensure_local_datetime(payload.get("ends_at"), _site_timezone_name(db, tenant_id, site_id)))
            if row.starts_at >= row.ends_at:
                raise ValueError("offshore.validation.invalid_period_range")
            if "status" in payload:
                row.status = _validate_status(payload.get("status"), WORK_PERIOD_STATUSES, "offshore.validation.invalid_period_status")
            if "notes" in payload:
                row.notes = _clean(payload.get("notes")) or None
            if "period_template_id" in payload:
                template_id = payload.get("period_template_id")
                if template_id is None:
                    row.period_template_id = None
                else:
                    template = self._get_template(db, int(tenant_id), str(site_id), int(template_id))
                    if template is None:
                        raise LookupError("offshore.validation.cross_site")
                    row.period_template_id = int(template_id)
            if "menu_cycle_id" in payload:
                menu_cycle_id = payload.get("menu_cycle_id")
                if menu_cycle_id is None:
                    row.menu_cycle_id = None
                else:
                    self._ensure_menu_cycle_scope(db, int(tenant_id), str(site_id), int(menu_cycle_id))
                    row.menu_cycle_id = int(menu_cycle_id)
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_service_events(self, tenant_id: int | None, site_id: str | None, work_period_id: int) -> list[OffshoreServiceEvent]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            return (
                self._base_query(db, OffshoreServiceEvent, int(tenant_id), str(site_id))
                .filter(OffshoreServiceEvent.work_period_id == int(work_period_id))
                .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                .all()
            )
        finally:
            db.close()

    def update_service_event(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, event_id: int, payload: dict[str, object]) -> OffshoreServiceEvent:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            row = self._get_service_event(db, int(tenant_id), str(site_id), int(event_id))
            if row is None or int(row.work_period_id) != int(work_period_id):
                raise LookupError("offshore.validation.cross_site")
            if "status" in payload:
                row.status = _validate_status(payload.get("status"), PERIOD_TEMPLATE_EVENT_STATUSES, "offshore.validation.invalid_event_status")
            if "display_name" in payload:
                row.display_name = _validate_name(payload.get("display_name"))
            if "service_code" in payload:
                row.service_code = _validate_name(payload.get("service_code"), key="offshore.validation.service_code_required")
            if "starts_at" in payload:
                row.starts_at = _utc_datetime(_ensure_local_datetime(payload.get("starts_at"), _site_timezone_name(db, tenant_id, site_id)))
            if "expected_portions" in payload:
                row.expected_portions = _validate_portions(payload.get("expected_portions"))
            if "work_position_id" in payload:
                work_position_id = payload.get("work_position_id")
                if work_position_id is None:
                    row.work_position_id = None
                else:
                    self._ensure_work_position_scope(db, int(tenant_id), str(site_id), int(work_position_id))
                    row.work_position_id = int(work_position_id)
            if "notes" in payload:
                row.notes = _clean(payload.get("notes")) or None
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def detect_period_overlaps(self, tenant_id: int | None, site_id: str | None) -> list[dict[str, object]]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            periods = (
                self._base_query(db, OffshoreWorkPeriod, int(tenant_id), str(site_id))
                .order_by(OffshoreWorkPeriod.starts_at.asc(), OffshoreWorkPeriod.id.asc())
                .all()
            )
            overlaps: list[dict[str, object]] = []
            for index, left in enumerate(periods):
                for right in periods[index + 1 :]:
                    if left.ends_at <= right.starts_at:
                        break
                    if left.starts_at < right.ends_at and right.starts_at < left.ends_at:
                        overlaps.append({"left": left, "right": right})
            return overlaps
        finally:
            db.close()

    def dashboard_summary(self, tenant_id: int | None, site_id: str | None) -> dict[str, object]:
        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            now = _now()
            templates = self.list_period_templates(tenant_id, site_id)
            current_period = (
                self._base_query(db, OffshoreWorkPeriod, int(tenant_id), str(site_id))
                .filter(OffshoreWorkPeriod.starts_at <= now, OffshoreWorkPeriod.ends_at > now, OffshoreWorkPeriod.status != "cancelled")
                .order_by(OffshoreWorkPeriod.starts_at.asc())
                .first()
            )
            next_period = (
                self._base_query(db, OffshoreWorkPeriod, int(tenant_id), str(site_id))
                .filter(OffshoreWorkPeriod.starts_at > now, OffshoreWorkPeriod.status == "planned")
                .order_by(OffshoreWorkPeriod.starts_at.asc())
                .first()
            )
            upcoming_event_count = (
                self._base_query(db, OffshoreServiceEvent, int(tenant_id), str(site_id))
                .filter(OffshoreServiceEvent.starts_at >= now, OffshoreServiceEvent.status != "cancelled")
                .count()
            )
            overlaps = self.detect_period_overlaps(tenant_id, site_id)
            return {
                "has_templates": bool(templates),
                "template_count": len(templates),
                "current_period": current_period,
                "next_period": next_period,
                "upcoming_event_count": int(upcoming_event_count),
                "overlap_warnings": overlaps,
            }
        finally:
            db.close()

    def create_work_period_from_template(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        period_template_id: int,
        starts_at: datetime | str,
        name: str | None = None,
        menu_cycle_id: int | None = None,
        notes: str | None = None,
    ) -> OffshorePeriodGeneration:
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            template = self._get_template(db, int(tenant_id), str(site_id), int(period_template_id))
            if template is None or not bool(template.active):
                raise LookupError("offshore.validation.cross_site")
            self._ensure_menu_cycle_scope(db, int(tenant_id), str(site_id), menu_cycle_id)
            timezone_name = _site_timezone_name(db, tenant_id, site_id)
            starts_local = _ensure_local_datetime(starts_at, timezone_name)
            ends_local = datetime.combine(starts_local.date() + timedelta(days=int(template.duration_days)), starts_local.timetz().replace(tzinfo=None), tzinfo=starts_local.tzinfo)
            starts_utc = _utc_datetime(starts_local)
            ends_utc = _utc_datetime(ends_local)
            if starts_utc >= ends_utc:
                raise ValueError("offshore.validation.invalid_period_range")
            period_name = _clean(name) or template.name
            existing = (
                self._base_query(db, OffshoreWorkPeriod, int(tenant_id), str(site_id))
                .filter(
                    OffshoreWorkPeriod.period_template_id == int(period_template_id),
                    OffshoreWorkPeriod.starts_at == starts_utc,
                    OffshoreWorkPeriod.menu_cycle_id == (int(menu_cycle_id) if menu_cycle_id is not None else None),
                )
                .first()
            )
            if existing is not None:
                existing_events = (
                    self._base_query(db, OffshoreServiceEvent, int(tenant_id), str(site_id))
                    .filter(OffshoreServiceEvent.work_period_id == int(existing.id))
                    .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                    .all()
                )
                return OffshorePeriodGeneration(work_period=existing, service_events=existing_events)
            period = OffshoreWorkPeriod(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                period_template_id=int(period_template_id),
                menu_cycle_id=int(menu_cycle_id) if menu_cycle_id is not None else None,
                name=period_name,
                starts_at=starts_utc,
                ends_at=ends_utc,
                status="planned",
                notes=_clean(notes) or None,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(period)
            db.flush()
            generated_events: list[OffshoreServiceEvent] = []
            active_events = self._active_template_events(db, int(period_template_id))
            for template_event in active_events:
                local_start = datetime.combine(starts_local.date() + timedelta(days=int(template_event.day_offset)), template_event.local_time, tzinfo=starts_local.tzinfo)
                event_utc = _utc_datetime(local_start)
                if not (starts_utc <= event_utc < ends_utc):
                    raise ValueError("offshore.validation.event_outside_period")
                self._ensure_work_position_scope(db, int(tenant_id), str(site_id), template_event.work_position_id)
                event = OffshoreServiceEvent(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    work_period_id=int(period.id),
                    source_template_event_id=int(template_event.id),
                    starts_at=event_utc,
                    service_code=template_event.service_code,
                    display_name=template_event.display_name,
                    work_position_id=template_event.work_position_id,
                    expected_portions=template_event.default_portions,
                    status="planned",
                    notes=template_event.notes,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(event)
                generated_events.append(event)
            db.commit()
            db.refresh(period)
            for event in generated_events:
                db.refresh(event)
            return OffshorePeriodGeneration(work_period=period, service_events=generated_events)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


_service = OffshorePeriodService()


def serialize_template_event(event: OffshorePeriodTemplateEvent, locale: str, template: OffshorePeriodTemplate | None = None) -> dict[str, object]:
    day_label = f"{t(locale, 'offshore.period.day')} {int(event.day_offset) + 1}"
    if template and template.start_weekday is not None:
        weekday = (int(template.start_weekday) + int(event.day_offset)) % 7
        day_label = f"{day_label} – {_weekday_name(locale, weekday)}"
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "site_id": event.site_id,
        "period_template_id": event.period_template_id,
        "day_offset": event.day_offset,
        "day_label": day_label,
        "local_time": event.local_time.strftime("%H:%M"),
        "service_code": event.service_code,
        "display_name": event.display_name,
        "work_position_id": event.work_position_id,
        "default_portions": event.default_portions,
        "notes": event.notes,
        "sort_order": event.sort_order,
        "active": bool(event.active),
    }


def serialize_template(template: OffshorePeriodTemplate, locale: str, events: list[OffshorePeriodTemplateEvent] | None = None) -> dict[str, object]:
    return {
        "id": template.id,
        "tenant_id": template.tenant_id,
        "site_id": template.site_id,
        "name": template.name,
        "description": template.description,
        "duration_days": template.duration_days,
        "start_weekday": template.start_weekday,
        "start_weekday_label": _weekday_name(locale, int(template.start_weekday)) if template.start_weekday is not None else None,
        "active": bool(template.active),
        "sort_order": template.sort_order,
        "events": [serialize_template_event(event, locale, template) for event in (events or [])],
    }


def serialize_period(period: OffshoreWorkPeriod, locale: str, timezone_name: str, events: list[OffshoreServiceEvent] | None = None) -> dict[str, object]:
    zone = _local_zone(timezone_name)
    local_starts = period.starts_at.astimezone(zone)
    local_ends = period.ends_at.astimezone(zone)
    return {
        "id": period.id,
        "tenant_id": period.tenant_id,
        "site_id": period.site_id,
        "period_template_id": period.period_template_id,
        "menu_cycle_id": period.menu_cycle_id,
        "name": period.name,
        "starts_at": period.starts_at,
        "ends_at": period.ends_at,
        "starts_at_local": local_starts.strftime("%Y-%m-%d %H:%M"),
        "ends_at_local": local_ends.strftime("%Y-%m-%d %H:%M"),
        "status": period.status,
        "notes": period.notes,
        "events": [serialize_service_event(event, locale, timezone_name) for event in (events or [])],
    }


def serialize_service_event(event: OffshoreServiceEvent, locale: str, timezone_name: str) -> dict[str, object]:
    zone = _local_zone(timezone_name)
    local_starts = event.starts_at.astimezone(zone)
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "site_id": event.site_id,
        "work_period_id": event.work_period_id,
        "source_template_event_id": event.source_template_event_id,
        "starts_at": event.starts_at,
        "starts_at_local": local_starts.strftime("%Y-%m-%d %H:%M"),
        "service_code": event.service_code,
        "display_name": event.display_name,
        "work_position_id": event.work_position_id,
        "expected_portions": event.expected_portions,
        "status": event.status,
        "notes": event.notes,
    }


def period_dashboard_payload(tenant_id: int | None, site_id: str | None, locale: str | None = None) -> dict[str, object]:
    summary = _service.dashboard_summary(tenant_id, site_id)
    db = get_session()
    try:
        _validate_scope(db, tenant_id, site_id)
        timezone_name = _site_timezone_name(db, tenant_id, site_id)
        current_period = summary.get("current_period")
        next_period = summary.get("next_period")
        current_events = (
            _service.list_service_events(tenant_id, site_id, int(current_period.id)) if current_period else []
        )
        next_events = _service.list_service_events(tenant_id, site_id, int(next_period.id)) if next_period else []
        templates = _service.list_period_templates(tenant_id, site_id)
        return {
            "timezone_name": timezone_name,
            "has_templates": bool(summary.get("has_templates")),
            "template_count": int(summary.get("template_count") or 0),
            "current_period": serialize_period(current_period, locale or "sv", timezone_name, current_events) if current_period else None,
            "next_period": serialize_period(next_period, locale or "sv", timezone_name, next_events) if next_period else None,
            "upcoming_event_count": int(summary.get("upcoming_event_count") or 0),
            "overlap_warnings": summary.get("overlap_warnings") or [],
            "templates": [serialize_template(template, locale or "sv", _service.list_template_events(tenant_id, site_id, int(template.id))) for template in templates],
        }
    finally:
        db.close()
