from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date as _date, datetime, time as _time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context, has_request_context, request, url_for
from sqlalchemy import text

from core.db import get_new_session, get_session

from .i18n import copy_for, normalize_locale
from .models import OffshoreInstallationSettings, OffshorePrepTask, OffshoreServiceEvent, OffshoreWorkPeriod, OffshoreWorkPosition
from .periods import _local_zone, site_timezone_name
from .permissions import can_write_prep


PREP_STATUS_PLANNED = "planned"
PREP_STATUS_IN_PROGRESS = "in_progress"
PREP_STATUS_COMPLETED = "completed"
PREP_STATUS_CANCELLED = "cancelled"
PREP_STATUSES = (PREP_STATUS_PLANNED, PREP_STATUS_IN_PROGRESS, PREP_STATUS_COMPLETED, PREP_STATUS_CANCELLED)


@dataclass(frozen=True, slots=True)
class OffshorePrepSummary:
    planned_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    cancelled_count: int = 0

    @property
    def total_count(self) -> int:
        return self.planned_count + self.in_progress_count + self.completed_count + self.cancelled_count

    @property
    def remaining_count(self) -> int:
        return self.planned_count + self.in_progress_count


@dataclass(frozen=True, slots=True)
class OffshorePrepTaskRead:
    id: int
    tenant_id: int
    site_id: str
    work_period_id: int
    service_event_id: int
    builder_component_id: str | None
    component_name_snapshot: str | None
    title: str
    instructions: str | None
    planned_date: str
    planned_time: str | None
    work_position_id: int | None
    work_position_label: str | None
    status: str
    sort_order: int
    created_by_user_id: int | None
    completed_by_user_id: int | None
    completed_at: str | None
    created_at: str | None
    updated_at: str | None
    component_label: str | None
    can_edit: bool = False
    can_transition: bool = False
    can_start: bool = False
    can_complete: bool = False
    can_reopen: bool = False
    can_cancel: bool = False


@dataclass(frozen=True, slots=True)
class OffshorePrepServiceGroup:
    service_event_id: int
    service_label: str
    service_code: str
    local_date: str
    local_start_time: str
    work_period_id: int
    work_period_name: str
    work_period_status: str
    event_status: str
    work_position_label: str | None
    detail_url: str
    prep_url: str
    can_write: bool
    summary: OffshorePrepSummary = field(default_factory=OffshorePrepSummary)
    tasks: tuple[OffshorePrepTaskRead, ...] = ()


@dataclass(frozen=True, slots=True)
class OffshorePrepDay:
    labels: dict[str, str]
    selected_date: str
    selected_date_label: str
    tenant_name: str | None
    site_name: str | None
    service_groups: tuple[OffshorePrepServiceGroup, ...]
    summary: OffshorePrepSummary
    state_key: str
    state_title: str
    state_body: str
    can_write: bool
    focus_service_event_id: int | None = None


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _safe_url(endpoint: str, **values: object) -> str:
    if has_request_context():
        return url_for(endpoint, **values)
    if endpoint == "offshore2.operations":
        return "/offshore/operations"
    if endpoint == "offshore2.operations_prep":
        return "/offshore/operations/prep"
    if endpoint == "offshore2.service_event_prep":
        service_event_id = values.get("service_event_id")
        return f"/offshore/service-events/{service_event_id}/prep"
    if endpoint == "offshore2.period_detail":
        period_id = values.get("period_id")
        return f"/offshore/periods/{period_id}"
    return "/offshore/operations"


def _parse_date(value: object | None) -> _date | None:
    raw = _clean(value)
    if not raw:
        return None
    return _date.fromisoformat(raw)


def _parse_time(value: object | None) -> _time | None:
    raw = _clean(value)
    if not raw:
        return None
    return _time.fromisoformat(raw)


def _parse_datetime(value: object | None) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _format_time(value: _time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _site_tenant_id(db, site_id: str) -> int | None:
    if not site_id:
        return None
    row = db.execute(
        text("SELECT tenant_id FROM sites WHERE id = :sid"),
        {"sid": site_id},
    ).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _validate_scope(db, tenant_id: int | None, site_id: str | None) -> None:
    if tenant_id is None or not site_id:
        raise ValueError("offshore.validation.missing_context")
    site_tenant_id = _site_tenant_id(db, site_id)
    if site_tenant_id is None or int(site_tenant_id) != int(tenant_id):
        raise LookupError("offshore.validation.cross_site")


def _component_label(component_id: str | None, snapshot: str | None) -> str | None:
    snapshot_value = _clean(snapshot)
    if snapshot_value:
        return snapshot_value
    component_id_value = _clean(component_id)
    if component_id_value:
        return f"Builderkomponent {component_id_value}"
    return None


def _normalize_status(value: object | None) -> str:
    return _clean(value).lower()


class OffshorePrepTaskService:
    def _base_query(self, db, tenant_id: int, site_id: str):
        return db.query(OffshorePrepTask).filter(
            OffshorePrepTask.tenant_id == int(tenant_id),
            OffshorePrepTask.site_id == str(site_id),
        )

    def _site_zone(self, db, tenant_id: int, site_id: str) -> ZoneInfo:
        try:
            return _local_zone(site_timezone_name(int(tenant_id), str(site_id)))
        except Exception:
            return ZoneInfo("Europe/Oslo")

    def _service_date(self, event: OffshoreServiceEvent, zone: ZoneInfo) -> _date:
        return event.starts_at.astimezone(zone).date()

    def _get_work_period(self, db, tenant_id: int, site_id: str, work_period_id: int) -> OffshoreWorkPeriod | None:
        return (
            db.query(OffshoreWorkPeriod)
            .filter(
                OffshoreWorkPeriod.tenant_id == int(tenant_id),
                OffshoreWorkPeriod.site_id == str(site_id),
                OffshoreWorkPeriod.id == int(work_period_id),
            )
            .first()
        )

    def _get_service_event(self, db, tenant_id: int, site_id: str, service_event_id: int) -> OffshoreServiceEvent | None:
        return (
            db.query(OffshoreServiceEvent)
            .filter(
                OffshoreServiceEvent.tenant_id == int(tenant_id),
                OffshoreServiceEvent.site_id == str(site_id),
                OffshoreServiceEvent.id == int(service_event_id),
            )
            .first()
        )

    def _get_work_position(self, db, tenant_id: int, site_id: str, work_position_id: int) -> OffshoreWorkPosition | None:
        return (
            db.query(OffshoreWorkPosition)
            .filter(
                OffshoreWorkPosition.tenant_id == int(tenant_id),
                OffshoreWorkPosition.site_id == str(site_id),
                OffshoreWorkPosition.id == int(work_position_id),
            )
            .first()
        )

    def _resolve_component_snapshot(self, component_ref: str | None, fallback_snapshot: str | None = None) -> str | None:
        ref = _clean(component_ref)
        if not ref:
            return _clean(fallback_snapshot) or None
        if not has_app_context():
            return _clean(fallback_snapshot) or None
        flow = current_app.extensions.get("builder_menu_context_flow")
        if flow is None:
            return _clean(fallback_snapshot) or None
        candidates: list[object] = []
        try:
            if hasattr(flow, "list_reusable_components_for_builder"):
                candidates = list(flow.list_reusable_components_for_builder(query=ref))
            elif hasattr(flow, "list_library_components"):
                candidates = list(flow.list_library_components())
        except Exception:
            candidates = []
        ref_lower = ref.lower()
        for candidate in candidates:
            candidate_id = _clean(getattr(candidate, "component_id", None))
            candidate_name = _clean(getattr(candidate, "canonical_name", None))
            if candidate_id.lower() == ref_lower or candidate_name.lower() == ref_lower:
                return candidate_name or _clean(fallback_snapshot) or None
        return _clean(fallback_snapshot) or None

    def _is_manager(self, role: str | None) -> bool:
        return _normalize_status(role) in {"editor", "admin", "superuser"}

    def _can_edit(self, *, role: str | None, task: OffshorePrepTask, user_id: int | None) -> bool:
        if self._is_manager(role):
            return True
        if not can_write_prep(role):
            return False
        return task.status != PREP_STATUS_COMPLETED and task.created_by_user_id == user_id

    def _can_transition(self, *, role: str | None, task: OffshorePrepTask, user_id: int | None, target_status: str) -> bool:
        if self._is_manager(role):
            return True
        if not can_write_prep(role):
            return False
        if task.created_by_user_id != user_id:
            return False
        return target_status in PREP_STATUSES

    def _status_summary(self, tasks: list[OffshorePrepTask]) -> OffshorePrepSummary:
        counts: dict[str, int] = defaultdict(int)
        for task in tasks:
            counts[_normalize_status(task.status)] += 1
        return OffshorePrepSummary(
            planned_count=int(counts.get(PREP_STATUS_PLANNED, 0)),
            in_progress_count=int(counts.get(PREP_STATUS_IN_PROGRESS, 0)),
            completed_count=int(counts.get(PREP_STATUS_COMPLETED, 0)),
            cancelled_count=int(counts.get(PREP_STATUS_CANCELLED, 0)),
        )

    def _load_work_position_labels(self, db, tenant_id: int, site_id: str, work_position_ids: set[int]) -> dict[int, str]:
        if not work_position_ids:
            return {}
        rows = (
            db.query(OffshoreWorkPosition)
            .filter(
                OffshoreWorkPosition.tenant_id == int(tenant_id),
                OffshoreWorkPosition.site_id == str(site_id),
                OffshoreWorkPosition.id.in_(sorted(work_position_ids)),
            )
            .all()
        )
        return {int(row.id): str(row.name) for row in rows}

    def _task_read(self, task: OffshorePrepTask, *, role: str | None, user_id: int | None, work_position_label: str | None = None) -> OffshorePrepTaskRead:
        can_edit = self._can_edit(role=role, task=task, user_id=user_id)
        can_transition = self._can_transition(role=role, task=task, user_id=user_id, target_status=_normalize_status(task.status)) or self._is_manager(role)
        status = _normalize_status(task.status)
        return OffshorePrepTaskRead(
            id=int(task.id),
            tenant_id=int(task.tenant_id),
            site_id=str(task.site_id),
            work_period_id=int(task.work_period_id),
            service_event_id=int(task.service_event_id),
            builder_component_id=_clean(task.builder_component_id) or None,
            component_name_snapshot=_clean(task.component_name_snapshot) or None,
            title=str(task.title),
            instructions=_clean(task.instructions) or None,
            planned_date=task.planned_date.isoformat(),
            planned_time=_format_time(task.planned_time),
            work_position_id=int(task.work_position_id) if task.work_position_id is not None else None,
            work_position_label=work_position_label,
            status=status,
            sort_order=int(task.sort_order),
            created_by_user_id=int(task.created_by_user_id) if task.created_by_user_id is not None else None,
            completed_by_user_id=int(task.completed_by_user_id) if task.completed_by_user_id is not None else None,
            completed_at=_format_dt(task.completed_at),
            created_at=_format_dt(task.created_at),
            updated_at=_format_dt(task.updated_at),
            component_label=_component_label(task.builder_component_id, task.component_name_snapshot),
            can_edit=can_edit,
            can_transition=can_transition,
            can_start=can_transition and status == PREP_STATUS_PLANNED,
            can_complete=can_transition and status in {PREP_STATUS_PLANNED, PREP_STATUS_IN_PROGRESS},
            can_reopen=can_transition and status in {PREP_STATUS_COMPLETED, PREP_STATUS_CANCELLED},
            can_cancel=can_transition and status in {PREP_STATUS_PLANNED, PREP_STATUS_IN_PROGRESS},
        )

    def _fetch_tasks(
        self,
        db,
        tenant_id: int,
        site_id: str,
        *,
        service_event_ids: set[int] | None = None,
        planned_date: _date | None = None,
    ) -> list[OffshorePrepTask]:
        query = self._base_query(db, tenant_id, site_id)
        if service_event_ids:
            query = query.filter(OffshorePrepTask.service_event_id.in_(sorted(service_event_ids)))
        if planned_date is not None:
            query = query.filter(OffshorePrepTask.planned_date == planned_date)
        return query.order_by(
            OffshorePrepTask.planned_date.asc(),
            OffshorePrepTask.planned_time.asc().nullslast(),
            OffshorePrepTask.sort_order.asc(),
            OffshorePrepTask.id.asc(),
        ).all()

    def summarize_service_events(self, *, tenant_id: int, site_id: str, service_event_ids: set[int]) -> dict[int, OffshorePrepSummary]:
        if not service_event_ids:
            return {}
        db = get_session()
        try:
            tasks = self._fetch_tasks(db, tenant_id, site_id, service_event_ids=service_event_ids)
        finally:
            db.close()
        grouped: dict[int, list[OffshorePrepTask]] = defaultdict(list)
        for task in tasks:
            grouped[int(task.service_event_id)].append(task)
        return {service_event_id: self._status_summary(items) for service_event_id, items in grouped.items()}

    def list_tasks_for_service_event(
        self,
        *,
        tenant_id: int,
        site_id: str,
        service_event_id: int,
        role: str | None,
        user_id: int | None,
    ) -> tuple[OffshorePrepTaskRead, ...]:
        db = get_session()
        try:
            service_event = self._get_service_event(db, tenant_id, site_id, service_event_id)
            if service_event is None:
                raise LookupError("offshore.validation.cross_site")
            tasks = self._fetch_tasks(db, tenant_id, site_id, service_event_ids={int(service_event_id)})
            work_position_ids = {int(task.work_position_id) for task in tasks if task.work_position_id is not None}
            work_position_labels = self._load_work_position_labels(db, tenant_id, site_id, work_position_ids)
            return tuple(
                self._task_read(
                    task,
                    role=role,
                    user_id=user_id,
                    work_position_label=work_position_labels.get(int(task.work_position_id)) if task.work_position_id is not None else None,
                )
                for task in tasks
            )
        finally:
            db.close()

    def build_day_view(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        selected_date: _date | None,
        locale: str | None,
        role: str | None,
        user_id: int | None,
        tenant_name: str | None = None,
        site_name: str | None = None,
        focus_service_event_id: int | None = None,
    ) -> OffshorePrepDay:
        locale_value = normalize_locale(locale or "sv")
        labels = copy_for(locale_value)
        can_write = can_write_prep(role)
        zone = ZoneInfo("Europe/Oslo")
        day_value = selected_date or datetime.now(zone).date()
        db = get_session()
        try:
            settings = None
            periods: list[OffshoreWorkPeriod] = []
            events: list[OffshoreServiceEvent] = []
            if tenant_id is not None and site_id:
                settings = (
                    db.query(OffshoreInstallationSettings)
                    .filter(OffshoreInstallationSettings.tenant_id == int(tenant_id), OffshoreInstallationSettings.site_id == str(site_id))
                    .first()
                )
                periods = (
                    db.query(OffshoreWorkPeriod)
                    .filter(OffshoreWorkPeriod.tenant_id == int(tenant_id), OffshoreWorkPeriod.site_id == str(site_id))
                    .order_by(OffshoreWorkPeriod.starts_at.asc(), OffshoreWorkPeriod.id.asc())
                    .all()
                )
                if settings is not None:
                    zone = self._site_zone(db, int(tenant_id), str(site_id))
                    day_value = selected_date or datetime.now(zone).date()
                    start_local = datetime.combine(day_value, _time.min, tzinfo=zone)
                    end_local = start_local + timedelta(days=1)
                    events = (
                        db.query(OffshoreServiceEvent)
                        .filter(
                            OffshoreServiceEvent.tenant_id == int(tenant_id),
                            OffshoreServiceEvent.site_id == str(site_id),
                            OffshoreServiceEvent.starts_at >= start_local.astimezone(UTC),
                            OffshoreServiceEvent.starts_at < end_local.astimezone(UTC),
                        )
                        .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                        .all()
                    )
        finally:
            db.close()

        if tenant_id is None or not site_id:
            return OffshorePrepDay(
                labels=labels,
                selected_date=day_value.isoformat(),
                selected_date_label=day_value.isoformat(),
                tenant_name=tenant_name,
                site_name=site_name,
                service_groups=(),
                summary=OffshorePrepSummary(),
                state_key="no_installation",
                state_title=labels["offshore.prep.no_installation"],
                state_body=labels["offshore.prep.no_installation"],
                can_write=False,
                focus_service_event_id=focus_service_event_id,
            )
        if settings is None:
            return OffshorePrepDay(
                labels=labels,
                selected_date=day_value.isoformat(),
                selected_date_label=day_value.isoformat(),
                tenant_name=tenant_name,
                site_name=site_name,
                service_groups=(),
                summary=OffshorePrepSummary(),
                state_key="no_installation",
                state_title=labels["offshore.prep.no_installation"],
                state_body=labels["offshore.prep.no_installation"],
                can_write=False,
                focus_service_event_id=focus_service_event_id,
            )
        if not periods:
            return OffshorePrepDay(
                labels=labels,
                selected_date=day_value.isoformat(),
                selected_date_label=day_value.isoformat(),
                tenant_name=tenant_name,
                site_name=site_name,
                service_groups=(),
                summary=OffshorePrepSummary(),
                state_key="no_period",
                state_title=labels["offshore.prep.no_period"],
                state_body=labels["offshore.prep.no_period"],
                can_write=can_write,
                focus_service_event_id=focus_service_event_id,
            )
        if not events:
            return OffshorePrepDay(
                labels=labels,
                selected_date=day_value.isoformat(),
                selected_date_label=day_value.isoformat(),
                tenant_name=tenant_name,
                site_name=site_name,
                service_groups=(),
                summary=OffshorePrepSummary(),
                state_key="no_service_events",
                state_title=labels["offshore.prep.no_service_events"],
                state_body=labels["offshore.prep.no_service_events"],
                can_write=can_write,
                focus_service_event_id=focus_service_event_id,
            )

        period_by_id = {int(period.id): period for period in periods}
        tasks = self._fetch_tasks(db, int(tenant_id), str(site_id), planned_date=day_value)
        grouped_tasks: dict[int, list[OffshorePrepTask]] = defaultdict(list)
        for task in tasks:
            grouped_tasks[int(task.service_event_id)].append(task)
        work_position_ids = {int(task.work_position_id) for task in tasks if task.work_position_id is not None}
        work_position_labels = self._load_work_position_labels(db, int(tenant_id), str(site_id), work_position_ids)
        summaries = {service_event_id: self._status_summary(items) for service_event_id, items in grouped_tasks.items()}
        service_groups: list[OffshorePrepServiceGroup] = []
        total_summary = OffshorePrepSummary()
        for event in events:
            period = period_by_id.get(int(event.work_period_id))
            if period is None:
                continue
            task_items = grouped_tasks.get(int(event.id), [])
            summary = summaries.get(int(event.id), OffshorePrepSummary())
            total_summary = OffshorePrepSummary(
                planned_count=total_summary.planned_count + summary.planned_count,
                in_progress_count=total_summary.in_progress_count + summary.in_progress_count,
                completed_count=total_summary.completed_count + summary.completed_count,
                cancelled_count=total_summary.cancelled_count + summary.cancelled_count,
            )
            zone_for_display = self._site_zone(db, int(tenant_id), str(site_id))
            readable_tasks = tuple(
                self._task_read(
                    task,
                    role=role,
                    user_id=user_id,
                    work_position_label=work_position_labels.get(int(task.work_position_id)) if task.work_position_id is not None else None,
                )
                for task in task_items
            )
            can_write_event = can_write and _normalize_status(event.status) not in {"completed", "cancelled"} and _normalize_status(period.status) not in {"completed", "cancelled"}
            service_groups.append(
                OffshorePrepServiceGroup(
                    service_event_id=int(event.id),
                    service_label=str(event.display_name),
                    service_code=str(event.service_code),
                    local_date=self._service_date(event, zone_for_display).isoformat(),
                    local_start_time=event.starts_at.astimezone(zone_for_display).strftime("%H:%M"),
                    work_period_id=int(period.id),
                    work_period_name=str(period.name),
                    work_period_status=str(period.status),
                    event_status=str(event.status),
                    work_position_label=work_position_labels.get(int(event.work_position_id)) if event.work_position_id is not None else None,
                    detail_url=_safe_url("offshore2.period_detail", period_id=int(period.id)),
                    prep_url=_safe_url("offshore2.operations_prep", date=day_value.isoformat(), service_event_id=int(event.id)),
                    can_write=can_write_event,
                    summary=summary,
                    tasks=readable_tasks,
                )
            )

        state_key = "normal" if service_groups else "no_service_events"
        state_title = labels["offshore.prep.empty"] if service_groups else labels["offshore.prep.no_service_events"]
        state_body = labels["offshore.prep.empty"] if service_groups else labels["offshore.prep.no_service_events"]
        return OffshorePrepDay(
            labels=labels,
            selected_date=day_value.isoformat(),
            selected_date_label=day_value.isoformat(),
            tenant_name=tenant_name,
            site_name=site_name,
            service_groups=tuple(service_groups),
            summary=total_summary,
            state_key=state_key,
            state_title=state_title,
            state_body=state_body,
            can_write=can_write,
            focus_service_event_id=focus_service_event_id,
        )

    def create_task(
        self,
        *,
        tenant_id: int,
        site_id: str,
        service_event_id: int,
        actor_user_id: int | None,
        role: str | None,
        payload: dict[str, Any],
    ) -> OffshorePrepTaskRead:
        if not can_write_prep(role):
            raise PermissionError("offshore.prep.forbidden")
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            service_event = self._get_service_event(db, tenant_id, site_id, service_event_id)
            if service_event is None:
                raise LookupError("offshore.validation.cross_site")
            period = self._get_work_period(db, tenant_id, site_id, int(service_event.work_period_id))
            if period is None or _normalize_status(service_event.status) in {"completed", "cancelled"}:
                raise ValueError("offshore.validation.invalid_status")
            zone = self._site_zone(db, tenant_id, site_id)
            service_date = self._service_date(service_event, zone)
            title = _clean(payload.get("title"))
            if not title:
                raise ValueError("offshore.validation.name_required")
            planned_date = _parse_date(payload.get("planned_date")) or service_date
            planned_time = _parse_time(payload.get("planned_time"))
            sort_order_raw = _clean(payload.get("sort_order"))
            sort_order = int(sort_order_raw) if sort_order_raw else 0
            if sort_order < 0:
                raise ValueError("offshore.validation.invalid_sort_order")
            work_position_id = payload.get("work_position_id")
            work_position = None
            if work_position_id not in (None, "", 0, "0"):
                work_position = self._get_work_position(db, tenant_id, site_id, int(work_position_id))
                if work_position is None:
                    raise LookupError("offshore.validation.cross_site")
            component_ref = _clean(payload.get("builder_component_id")) or None
            snapshot = self._resolve_component_snapshot(component_ref, payload.get("component_name_snapshot"))
            task = OffshorePrepTask(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                work_period_id=int(period.id),
                service_event_id=int(service_event.id),
                builder_component_id=component_ref,
                component_name_snapshot=snapshot,
                title=title,
                instructions=_clean(payload.get("instructions")) or None,
                planned_date=planned_date,
                planned_time=planned_time,
                work_position_id=int(work_position.id) if work_position is not None else None,
                status=PREP_STATUS_PLANNED,
                sort_order=sort_order,
                created_by_user_id=actor_user_id,
                completed_by_user_id=None,
                completed_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            position_label = work_position.name if work_position is not None else None
            return self._task_read(task, role=role, user_id=actor_user_id, work_position_label=position_label)
        finally:
            db.close()

    def update_task(
        self,
        *,
        tenant_id: int,
        site_id: str,
        task_id: int,
        actor_user_id: int | None,
        role: str | None,
        payload: dict[str, Any],
    ) -> OffshorePrepTaskRead:
        if not can_write_prep(role):
            raise PermissionError("offshore.prep.forbidden")
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            task = self._base_query(db, tenant_id, site_id).filter(OffshorePrepTask.id == int(task_id)).first()
            if task is None:
                raise LookupError("offshore.validation.cross_site")
            if not self._can_edit(role=role, task=task, user_id=actor_user_id):
                raise PermissionError("offshore.prep.forbidden")
            expected = _parse_datetime(payload.get("updated_at"))
            if expected is not None and task.updated_at is not None and task.updated_at.astimezone(UTC) != expected.astimezone(UTC):
                raise LookupError("offshore.validation.concurrent_update")
            if "title" in payload:
                title = _clean(payload.get("title"))
                if not title:
                    raise ValueError("offshore.validation.name_required")
                task.title = title
            if "instructions" in payload:
                task.instructions = _clean(payload.get("instructions")) or None
            if "planned_date" in payload:
                planned_date = _parse_date(payload.get("planned_date"))
                if planned_date is None:
                    raise ValueError("offshore.validation.invalid_date")
                task.planned_date = planned_date
            if "planned_time" in payload:
                task.planned_time = _parse_time(payload.get("planned_time"))
            if "sort_order" in payload:
                sort_order_raw = _clean(payload.get("sort_order"))
                sort_order = int(sort_order_raw) if sort_order_raw else 0
                if sort_order < 0:
                    raise ValueError("offshore.validation.invalid_sort_order")
                task.sort_order = sort_order
            if self._is_manager(role) and "work_position_id" in payload:
                work_position_id = payload.get("work_position_id")
                if work_position_id in (None, "", 0, "0"):
                    task.work_position_id = None
                else:
                    work_position = self._get_work_position(db, tenant_id, site_id, int(work_position_id))
                    if work_position is None:
                        raise LookupError("offshore.validation.cross_site")
                    task.work_position_id = int(work_position.id)
            if self._is_manager(role) and "builder_component_id" in payload:
                component_ref = _clean(payload.get("builder_component_id")) or None
                task.builder_component_id = component_ref
                task.component_name_snapshot = self._resolve_component_snapshot(component_ref, payload.get("component_name_snapshot"))
            elif "component_name_snapshot" in payload:
                task.component_name_snapshot = _clean(payload.get("component_name_snapshot")) or None
            task.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(task)
            position_label = None
            if task.work_position_id is not None:
                position = self._get_work_position(db, tenant_id, site_id, int(task.work_position_id))
                position_label = position.name if position is not None else None
            return self._task_read(task, role=role, user_id=actor_user_id, work_position_label=position_label)
        finally:
            db.close()

    def transition_task(
        self,
        *,
        tenant_id: int,
        site_id: str,
        task_id: int,
        actor_user_id: int | None,
        role: str | None,
        new_status: str,
        expected_updated_at: str | None = None,
    ) -> OffshorePrepTaskRead:
        if not can_write_prep(role):
            raise PermissionError("offshore.prep.forbidden")
        target_status = _normalize_status(new_status)
        if target_status not in PREP_STATUSES:
            raise ValueError("offshore.validation.invalid_status")
        allowed_transitions = {
            PREP_STATUS_PLANNED: {PREP_STATUS_IN_PROGRESS, PREP_STATUS_COMPLETED, PREP_STATUS_CANCELLED},
            PREP_STATUS_IN_PROGRESS: {PREP_STATUS_PLANNED, PREP_STATUS_COMPLETED, PREP_STATUS_CANCELLED},
            PREP_STATUS_COMPLETED: {PREP_STATUS_PLANNED, PREP_STATUS_IN_PROGRESS},
            PREP_STATUS_CANCELLED: {PREP_STATUS_PLANNED},
        }
        db = get_new_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            task = self._base_query(db, tenant_id, site_id).filter(OffshorePrepTask.id == int(task_id)).first()
            if task is None:
                raise LookupError("offshore.validation.cross_site")
            if not self._can_transition(role=role, task=task, user_id=actor_user_id, target_status=target_status):
                raise PermissionError("offshore.prep.forbidden")
            current_status = _normalize_status(task.status)
            if target_status not in allowed_transitions.get(current_status, set()):
                raise ValueError("offshore.validation.invalid_status_transition")
            expected = _parse_datetime(expected_updated_at)
            if expected is not None and task.updated_at is not None and task.updated_at.astimezone(UTC) != expected.astimezone(UTC):
                raise LookupError("offshore.validation.concurrent_update")
            task.status = target_status
            if target_status == PREP_STATUS_COMPLETED:
                task.completed_at = datetime.now(UTC)
                task.completed_by_user_id = actor_user_id
            else:
                task.completed_at = None
                task.completed_by_user_id = None
            task.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(task)
            position_label = None
            if task.work_position_id is not None:
                position = self._get_work_position(db, tenant_id, site_id, int(task.work_position_id))
                position_label = position.name if position is not None else None
            return self._task_read(task, role=role, user_id=actor_user_id, work_position_label=position_label)
        finally:
            db.close()


_service = OffshorePrepTaskService()