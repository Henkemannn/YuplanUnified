from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date as _date, datetime, time as _time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context, has_request_context, request, url_for

from core.calendar import CalendarItemMetadata, CalendarItemRead
from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.db import get_session
from core.models import CommunBuilderPublicationPin

from .i18n import copy_for, normalize_locale, t
from .models import (
    OffshoreInstallationSettings,
    OffshoreServiceEvent,
    OffshoreServiceEventMenuContext,
    OffshoreWorkPeriod,
    OffshoreWorkPosition,
)
from .periods import _local_zone, site_timezone_name


OPS_PERIOD_KIND_CURRENT = "current"
OPS_PERIOD_KIND_UPCOMING = "upcoming"
OPS_PERIOD_KIND_NONE = "none"

OPS_DAY_STATE_NO_EVENTS = "no_events"
OPS_DAY_STATE_ALL_FINISHED = "all_finished"
OPS_DAY_STATE_MISSING_CONTEXT = "missing_context"
OPS_DAY_STATE_UNAVAILABLE = "menu_unavailable"
OPS_DAY_STATE_UNRESOLVED = "menu_unresolved"
OPS_DAY_STATE_RESOLVED = "resolved"


def _today_in_zone(zone: ZoneInfo) -> _date:
    return datetime.now(zone).date()


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _format_date(value: _date) -> str:
    return value.isoformat()


def _format_local_dt(value: datetime, zone: ZoneInfo) -> str:
    return value.astimezone(zone).strftime("%Y-%m-%d %H:%M")


def _format_local_time(value: datetime, zone: ZoneInfo) -> str:
    return value.astimezone(zone).strftime("%H:%M")


def _local_midnight(value: _date, zone: ZoneInfo) -> datetime:
    return datetime.combine(value, _time.min, tzinfo=zone)


def _utc_window_for_date(value: _date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = _local_midnight(value, zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _safe_role(value: str | None) -> str | None:
    candidate = _clean(value).lower()
    return candidate or None


def _can_manage(role: str | None) -> bool:
    return _safe_role(role) in {"admin", "superuser", "editor"}


def _safe_menu_title(menu_id: str | None, title: str | None) -> str | None:
    cleaned_title = _clean(title)
    if cleaned_title:
        return cleaned_title
    cleaned_id = _clean(menu_id)
    if cleaned_id:
        return f"Builder menu {cleaned_id}"
    return None


def _safe_url(endpoint: str, **values: object) -> str:
    if has_request_context():
        return url_for(endpoint, **values)
    if endpoint == "offshore2.period_detail":
        return f"/offshore/periods/{values.get('period_id')}"
    if endpoint == "offshore2.periods":
        return "/offshore/periods"
    if endpoint == "offshore2.settings":
        return "/offshore/settings"
    if endpoint == "offshore2.operations":
        return "/offshore/operations"
    return "/offshore"


def _resolve_builder_menu_titles(menu_ids: set[str]) -> dict[str, str | None]:
    if not menu_ids or not has_app_context():
        return {}
    flow = current_app.extensions.get("builder_menu_context_flow")
    if flow is None:
        return {}
    try:
        menus = flow.list_menus()
    except Exception:
        return {}
    titles: dict[str, str | None] = {}
    for menu in menus:
        menu_id = _clean(getattr(menu, "menu_id", None))
        if menu_id in menu_ids:
            titles[menu_id] = _safe_menu_title(menu_id, getattr(menu, "title", None))
    return titles


@dataclass(frozen=True, slots=True)
class OffshoreOperationalPeriodSummary:
    kind: str
    title: str
    name: str | None
    status: str | None
    starts_at_local: str | None
    ends_at_local: str | None
    site_name: str | None
    position_labels: tuple[str, ...] = ()
    selected_date_in_period: bool = False
    detail_url: str | None = None
    manage_url: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class OffshoreOperationalServiceItem:
    service_event_id: int
    local_date: str
    local_start_time: str
    service_label: str
    service_code: str
    event_status: str
    work_period_id: int
    work_period_name: str
    work_period_status: str
    work_position_label: str | None
    menu_title: str | None
    builder_menu_identity: str | None
    builder_menu_version: int | None
    menu_context_status: str | None
    assignment_source: str | None
    resolution_reason: str | None
    detail_url: str
    manage_url: str | None
    editable: bool
    has_menu_context: bool
    calendar_item: CalendarItemRead


@dataclass(frozen=True, slots=True)
class OffshoreOperationalDay:
    local_date: str
    label: str
    state_key: str
    state_title: str
    state_body: str
    services: tuple[OffshoreOperationalServiceItem, ...] = ()
    service_count: int = 0


@dataclass(frozen=True, slots=True)
class OffshoreOperationalUpcomingDay:
    local_date: str
    label: str
    services: tuple[OffshoreOperationalServiceItem, ...] = ()
    service_count: int = 0


class OffshoreOperationsService:
    def __init__(self, *, publication_repository: CommunBuilderPublicationRepository | None = None) -> None:
        self._publication_repository = publication_repository or CommunBuilderPublicationRepository()

    def _load_context(self, db, tenant_id: int, site_id: str):
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
        return settings, periods

    def _resolve_period(self, periods: list[OffshoreWorkPeriod], selected_date: _date, zone: ZoneInfo) -> tuple[str, OffshoreWorkPeriod | None]:
        selected_start = _local_midnight(selected_date, zone)
        selected_end = selected_start + timedelta(days=1)

        def _contains(period: OffshoreWorkPeriod) -> bool:
            return period.starts_at.astimezone(zone) < selected_end and period.ends_at.astimezone(zone) > selected_start

        active = [period for period in periods if _contains(period) and str(period.status).lower() == "active"]
        if active:
            return OPS_PERIOD_KIND_CURRENT, active[0]
        planned = [period for period in periods if _contains(period) and str(period.status).lower() == "planned"]
        if planned:
            return OPS_PERIOD_KIND_CURRENT, planned[0]
        upcoming = [period for period in periods if period.starts_at.astimezone(zone).date() > selected_date and str(period.status).lower() != "cancelled"]
        if upcoming:
            return OPS_PERIOD_KIND_UPCOMING, upcoming[0]
        return OPS_PERIOD_KIND_NONE, None

    def _period_summary(self, period: OffshoreWorkPeriod | None, *, kind: str, selected_date: _date, zone: ZoneInfo, site_name: str | None, can_manage: bool) -> OffshoreOperationalPeriodSummary:
        if period is None:
            return OffshoreOperationalPeriodSummary(
                kind=OPS_PERIOD_KIND_NONE,
                title="No applicable period",
                name=None,
                status=None,
                starts_at_local=None,
                ends_at_local=None,
                site_name=site_name,
                position_labels=(),
                selected_date_in_period=False,
                detail_url=None,
                manage_url=_safe_url("offshore2.periods") if can_manage else None,
                note=None,
            )

        db = get_session()
        try:
            events = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(period.tenant_id),
                    OffshoreServiceEvent.site_id == str(period.site_id),
                    OffshoreServiceEvent.work_period_id == int(period.id),
                )
                .all()
            )
            position_ids = {int(event.work_position_id) for event in events if event.work_position_id is not None}
            position_labels = tuple(
                label
                for label in (
                    [row.name for row in db.query(OffshoreWorkPosition).filter(OffshoreWorkPosition.id.in_(position_ids)).all()]
                    if position_ids
                    else []
                )
                if _clean(label)
            )
        finally:
            db.close()

        title_key = {
            OPS_PERIOD_KIND_CURRENT: "Current work period",
            OPS_PERIOD_KIND_UPCOMING: "Upcoming work period",
        }.get(kind, "No applicable period")
        selected_start = _local_midnight(selected_date, zone)
        starts_local = period.starts_at.astimezone(zone)
        ends_local = period.ends_at.astimezone(zone)
        return OffshoreOperationalPeriodSummary(
            kind=kind,
            title=title_key,
            name=str(period.name),
            status=str(period.status),
            starts_at_local=_format_local_dt(period.starts_at, zone),
            ends_at_local=_format_local_dt(period.ends_at, zone),
            site_name=site_name,
            position_labels=position_labels,
            selected_date_in_period=starts_local <= selected_start < ends_local,
            detail_url=_safe_url("offshore2.period_detail", period_id=int(period.id)),
            manage_url=_safe_url("offshore2.period_detail", period_id=int(period.id)) if can_manage else None,
            note=None,
        )

    def _load_context_rows(self, tenant_id: int, site_id: str, period_ids: set[int]) -> dict[int, OffshoreServiceEventMenuContext]:
        if not period_ids:
            return {}
        db = get_session()
        try:
            rows = (
                db.query(OffshoreServiceEventMenuContext)
                .filter(
                    OffshoreServiceEventMenuContext.tenant_id == int(tenant_id),
                    OffshoreServiceEventMenuContext.site_id == str(site_id),
                    OffshoreServiceEventMenuContext.work_period_id.in_(sorted(period_ids)),
                )
                .order_by(
                    OffshoreServiceEventMenuContext.service_date.asc(),
                    OffshoreServiceEventMenuContext.service_event_id.asc(),
                )
                .all()
            )
            return {int(row.service_event_id): row for row in rows}
        finally:
            db.close()

    def _load_work_position_labels(self, tenant_id: int, site_id: str, work_position_ids: set[int]) -> dict[int, str]:
        if not work_position_ids:
            return {}
        db = get_session()
        try:
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
        finally:
            db.close()

    def _service_item(
        self,
        *,
        event: OffshoreServiceEvent,
        period: OffshoreWorkPeriod,
        context: OffshoreServiceEventMenuContext | None,
        zone: ZoneInfo,
        work_position_label: str | None,
        menu_title_map: dict[str, str | None],
        labels: dict[str, str],
        can_manage: bool,
    ) -> OffshoreOperationalServiceItem:
        starts_local = event.starts_at.astimezone(zone)
        status = str(context.resolution_status if context is not None else "missing")
        assignment_source = str(context.assignment_source) if context is not None else None
        resolution_reason = getattr(context, "resolution_reason", None)
        builder_menu_identity = None
        menu_title = None
        if context is not None and _clean(context.builder_menu_id):
            builder_menu_identity = f"{context.builder_menu_id} v{int(context.builder_menu_version or 0)}" if context.builder_menu_version is not None else str(context.builder_menu_id)
            menu_title = menu_title_map.get(str(context.builder_menu_id)) or _safe_menu_title(str(context.builder_menu_id), None)

        if context is None:
            resolution_reason = None
        elif status == "unresolved" and not resolution_reason:
            resolution_reason = labels["offshore.operations.resolution_unresolved_reason"]
        elif status == "unavailable" and not resolution_reason:
            resolution_reason = labels["offshore.operations.resolution_unavailable_reason"]

        calendar_item = CalendarItemRead(
            source_module="offshore",
            source_type="service_event",
            source_id=str(event.id),
            tenant_id=int(event.tenant_id),
            site_id=str(event.site_id),
            starts_at=event.starts_at if event.starts_at.tzinfo is not None else event.starts_at.replace(tzinfo=UTC),
            ends_at=None,
            all_day=False,
            title=str(event.display_name),
            category="service_event",
            status=str(event.status),
            detail_url=_safe_url("offshore2.period_detail", period_id=int(period.id)),
            editable=bool(can_manage and str(period.status).lower() != "completed"),
            priority=None,
            audience=None,
            visibility="site",
            related_entity_type="work_period",
            related_entity_id=int(period.id),
            metadata=CalendarItemMetadata(menu_context_status=status if context is not None else None),
        )
        return OffshoreOperationalServiceItem(
            service_event_id=int(event.id),
            local_date=_format_date(starts_local.date()),
            local_start_time=starts_local.strftime("%H:%M"),
            service_label=str(event.display_name),
            service_code=str(event.service_code),
            event_status=str(event.status),
            work_period_id=int(period.id),
            work_period_name=str(period.name),
            work_period_status=str(period.status),
            work_position_label=work_position_label,
            menu_title=menu_title,
            builder_menu_identity=builder_menu_identity,
            builder_menu_version=int(context.builder_menu_version) if context is not None and context.builder_menu_version is not None else None,
            menu_context_status=status if context is not None else None,
            assignment_source=assignment_source,
            resolution_reason=resolution_reason,
            detail_url=_safe_url("offshore2.period_detail", period_id=int(period.id)),
            manage_url=_safe_url("offshore2.period_detail", period_id=int(period.id)) if can_manage else None,
            editable=bool(can_manage and str(period.status).lower() != "completed"),
            has_menu_context=context is not None,
            calendar_item=calendar_item,
        )

    def build_view_model(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        selected_date: _date | None = None,
        locale: str | None = None,
        theme: str | None = None,
        role: str | None = None,
        tenant_name: str | None = None,
        site_name: str | None = None,
    ) -> dict[str, object]:
        locale_value = normalize_locale(locale or "sv")
        labels = copy_for(locale_value)
        can_manage = _can_manage(role)

        db = get_session()
        try:
            settings = None
            periods: list[OffshoreWorkPeriod] = []
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
        finally:
            db.close()

        timezone_name = "Europe/Oslo"
        if tenant_id is not None and site_id:
            try:
                timezone_name = site_timezone_name(tenant_id, site_id)
            except Exception:
                timezone_name = "Europe/Oslo"
        zone = _local_zone(timezone_name)
        selected_date_value = selected_date or _today_in_zone(zone)
        period_kind, relevant_period = self._resolve_period(periods, selected_date_value, zone)

        day_start_utc, day_end_utc = _utc_window_for_date(selected_date_value, zone)
        day_next_date = selected_date_value + timedelta(days=1)
        upcoming_cap_date = selected_date_value + timedelta(days=7)
        if relevant_period is not None:
            relevant_end_date = relevant_period.ends_at.astimezone(zone).date()
            if period_kind == OPS_PERIOD_KIND_CURRENT:
                upcoming_start_date = day_next_date
            else:
                upcoming_start_date = max(day_next_date, relevant_period.starts_at.astimezone(zone).date())
            upcoming_end_date = min(relevant_end_date, upcoming_cap_date)
            if upcoming_end_date < upcoming_start_date:
                upcoming_end_date = upcoming_start_date
        else:
            upcoming_start_date = day_next_date
            upcoming_end_date = day_next_date

        if relevant_period is not None:
            query_end_utc = _local_midnight(upcoming_end_date + timedelta(days=1), zone).astimezone(UTC)
        else:
            query_end_utc = day_end_utc

        db = get_session()
        try:
            events = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.starts_at >= day_start_utc,
                    OffshoreServiceEvent.starts_at < query_end_utc,
                )
                .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                .all()
            ) if tenant_id is not None and site_id else []
        finally:
            db.close()

        day_events = [event for event in events if event.starts_at.astimezone(zone).date() == selected_date_value]
        upcoming_events = [event for event in events if event.starts_at.astimezone(zone).date() > selected_date_value]

        period_ids = {int(event.work_period_id) for event in events}
        contexts_by_event_id = self._load_context_rows(int(tenant_id or 0), str(site_id or ""), period_ids) if period_ids else {}
        work_position_ids = {int(event.work_position_id) for event in events if event.work_position_id is not None}
        work_position_labels = self._load_work_position_labels(int(tenant_id or 0), str(site_id or ""), work_position_ids) if work_position_ids else {}
        builder_menu_ids = {
            str(context.builder_menu_id)
            for context in contexts_by_event_id.values()
            if context is not None and _clean(context.builder_menu_id)
        }
        menu_title_map = _resolve_builder_menu_titles(builder_menu_ids)

        selected_period = relevant_period
        day_service_items = [
            self._service_item(
                event=event,
                period=next(period for period in periods if int(period.id) == int(event.work_period_id)),
                context=contexts_by_event_id.get(int(event.id)),
                zone=zone,
                work_position_label=work_position_labels.get(int(event.work_position_id)) if event.work_position_id is not None else None,
                menu_title_map=menu_title_map,
                labels=labels,
                can_manage=can_manage,
            )
            for event in day_events
        ]
        upcoming_service_items = [
            self._service_item(
                event=event,
                period=next(period for period in periods if int(period.id) == int(event.work_period_id)),
                context=contexts_by_event_id.get(int(event.id)),
                zone=zone,
                work_position_label=work_position_labels.get(int(event.work_position_id)) if event.work_position_id is not None else None,
                menu_title_map=menu_title_map,
                labels=labels,
                can_manage=can_manage,
            )
            for event in upcoming_events
        ]

        periods_by_id = {int(period.id): period for period in periods}
        selected_period_summary = self._period_summary(
            selected_period,
            kind=period_kind,
            selected_date=selected_date_value,
            zone=zone,
            site_name=site_name,
            can_manage=can_manage,
        )
        current_period_summary = selected_period_summary if period_kind == OPS_PERIOD_KIND_CURRENT else None
        upcoming_period_summary = selected_period_summary if period_kind == OPS_PERIOD_KIND_UPCOMING else None

        day_state_key = OPS_DAY_STATE_NO_EVENTS
        day_state_title = labels["offshore.operations.no_service_title"]
        day_state_body = labels["offshore.operations.no_service_body"]
        if day_service_items:
            if all(item.event_status.lower() in {"completed", "cancelled"} for item in day_service_items):
                day_state_key = OPS_DAY_STATE_ALL_FINISHED
                day_state_title = labels["offshore.operations.all_services_finished_title"]
                day_state_body = labels["offshore.operations.all_services_finished_body"]
            elif any(not item.has_menu_context for item in day_service_items):
                day_state_key = OPS_DAY_STATE_MISSING_CONTEXT
                day_state_title = labels["offshore.operations.missing_context_title"]
                day_state_body = labels["offshore.operations.missing_context_body"]
            elif any(item.menu_context_status == "unavailable" for item in day_service_items):
                day_state_key = OPS_DAY_STATE_UNAVAILABLE
                day_state_title = labels["offshore.operations.menu_unavailable_title"]
                day_state_body = labels["offshore.operations.menu_unavailable_body"]
            elif any(item.menu_context_status == "unresolved" for item in day_service_items):
                day_state_key = OPS_DAY_STATE_UNRESOLVED
                day_state_title = labels["offshore.operations.menu_unresolved_title"]
                day_state_body = labels["offshore.operations.menu_unresolved_body"]
            else:
                day_state_key = OPS_DAY_STATE_RESOLVED
                day_state_title = labels["offshore.operations.resolved_day_title"]
                day_state_body = labels["offshore.operations.resolved_day_body"]

        upcoming_days: list[OffshoreOperationalUpcomingDay] = []
        if relevant_period is not None and upcoming_service_items:
            grouped: dict[str, list[OffshoreOperationalServiceItem]] = defaultdict(list)
            for item in upcoming_service_items:
                grouped[item.local_date].append(item)
            for local_date in sorted(grouped.keys()):
                upcoming_days.append(
                    OffshoreOperationalUpcomingDay(
                        local_date=local_date,
                        label=labels["offshore.operations.today"] if local_date == _format_date(selected_date_value) else local_date,
                        services=tuple(grouped[local_date]),
                        service_count=len(grouped[local_date]),
                    )
                )

        state_key = "normal"
        if settings is None:
            state_key = "no_installation"
        elif selected_period is None:
            state_key = "no_applicable_period"
        elif period_kind == OPS_PERIOD_KIND_UPCOMING:
            state_key = "upcoming_period_only"
        elif not day_service_items:
            state_key = "period_no_services"
        elif day_state_key != OPS_DAY_STATE_RESOLVED:
            state_key = day_state_key

        view_model: dict[str, object] = {
            "lang": locale_value,
            "theme": theme or "system",
            "labels": labels,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "tenant_name": tenant_name,
            "site_name": site_name,
            "user_name": (
                current_app.config.get("_offshore_role") if has_app_context() else None
            ) or (request.headers.get("X-User-Role") if has_request_context() else None) or "Inloggad",
            "user_role": role,
            "allow_site_switch": _can_manage(role),
            "can_manage": can_manage,
            "page_title": labels["offshore.operations.title"],
            "page_subtitle": labels["offshore.operations.subtitle"],
            "timezone_name": timezone_name,
            "installation_status": labels["offshore.dashboard.installation.configured"] if settings else labels["offshore.dashboard.installation.not_configured"],
            "selected_date": _format_date(selected_date_value),
            "selected_date_label": labels["offshore.operations.today"] if selected_date_value == _today_in_zone(zone) else _format_date(selected_date_value),
            "previous_date": _format_date(selected_date_value - timedelta(days=1)),
            "next_date": _format_date(selected_date_value + timedelta(days=1)),
            "operations_url": _safe_url("offshore2.operations"),
            "day": OffshoreOperationalDay(
                local_date=_format_date(selected_date_value),
                label=labels["offshore.operations.today"] if selected_date_value == _today_in_zone(zone) else _format_date(selected_date_value),
                state_key=day_state_key,
                state_title=day_state_title,
                state_body=day_state_body,
                services=tuple(day_service_items),
                service_count=len(day_service_items),
            ),
            "current_period_summary": current_period_summary,
            "upcoming_period_summary": upcoming_period_summary,
            "upcoming_days": tuple(upcoming_days),
            "state_key": state_key,
            "state_title": {
                "no_installation": labels["offshore.operations.no_installation_title"],
                "no_applicable_period": labels["offshore.operations.no_applicable_period_title"],
                "upcoming_period_only": labels["offshore.operations.upcoming_period_only_title"],
                "period_no_services": labels["offshore.operations.period_no_services_title"],
                OPS_DAY_STATE_NO_EVENTS: labels["offshore.operations.no_service_title"],
                OPS_DAY_STATE_ALL_FINISHED: labels["offshore.operations.all_services_finished_title"],
                OPS_DAY_STATE_MISSING_CONTEXT: labels["offshore.operations.missing_context_title"],
                OPS_DAY_STATE_UNAVAILABLE: labels["offshore.operations.menu_unavailable_title"],
                OPS_DAY_STATE_UNRESOLVED: labels["offshore.operations.menu_unresolved_title"],
                OPS_DAY_STATE_RESOLVED: labels["offshore.operations.resolved_day_title"],
                "normal": labels["offshore.operations.resolved_day_title"],
            }.get(state_key, labels["offshore.operations.resolved_day_title"]),
            "state_body": {
                "no_installation": labels["offshore.operations.no_installation_body"],
                "no_applicable_period": labels["offshore.operations.no_applicable_period_body"],
                "upcoming_period_only": labels["offshore.operations.upcoming_period_only_body"],
                "period_no_services": labels["offshore.operations.period_no_services_body"],
                OPS_DAY_STATE_NO_EVENTS: labels["offshore.operations.no_service_body"],
                OPS_DAY_STATE_ALL_FINISHED: labels["offshore.operations.all_services_finished_body"],
                OPS_DAY_STATE_MISSING_CONTEXT: labels["offshore.operations.missing_context_body"],
                OPS_DAY_STATE_UNAVAILABLE: labels["offshore.operations.menu_unavailable_body"],
                OPS_DAY_STATE_UNRESOLVED: labels["offshore.operations.menu_unresolved_body"],
                OPS_DAY_STATE_RESOLVED: labels["offshore.operations.resolved_day_body"],
                "normal": labels["offshore.operations.resolved_day_body"],
            }.get(state_key, labels["offshore.operations.resolved_day_body"]),
            "today_service_count": len(day_service_items),
            "unresolved_count": len([item for item in day_service_items if item.menu_context_status not in (None, "resolved")]),
            "current_period_kind": period_kind,
        }
        return view_model


_service = OffshoreOperationsService()
