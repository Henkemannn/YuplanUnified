from __future__ import annotations

from datetime import UTC, date as _date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

from core.db import get_session
from core.planera_v2.contracts import (
    EffectiveMenuReadiness,
    EffectiveMenuSourceType,
    EffectivePlanningMenuItem,
    PlanningComponentReference,
    PlanningCompositionOption,
    PlanningCompositionReference,
    PlanningMenuContext,
    PlanningOperationalDecisionReference,
    PlanningPublicationReference,
    PlanningServiceEvent,
    PlanningTrackDefinition,
    PlanningWorkPeriodReference,
    build_capabilities,
)

from .i18n import copy_for, normalize_locale, t
from .menu_context import _service as _menu_context_service, _validate_scope
from .models import OffshoreInstallationSettings, OffshoreServiceEvent, OffshoreWorkMenuDecision, OffshoreWorkPeriod
from .periods import _local_zone, site_timezone_name


ADAPTER_VERSION = "offshore-effective-menu/v1"


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _weekday_key(value: _date) -> str:
    return ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[value.weekday()]


def _local_midnight(value: _date, zone: ZoneInfo) -> datetime:
    return datetime.combine(value, datetime.min.time(), tzinfo=zone)


def _resolve_service_slot(event: OffshoreServiceEvent) -> str:
    text = f"{event.service_code} {event.display_name}".strip().lower()
    if any(token in text for token in ("dinner", "middag", "kväll", "kvall")):
        return "dinner"
    return "lunch"


def _safe_title(value: object | None) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _parse_visibility_json(raw_value: str | None, locale: str) -> tuple[tuple[str, tuple[PlanningTrackDefinition, ...]], ...]:
    candidate = _clean(raw_value)
    if not candidate:
        return ()
    try:
        parsed = json.loads(candidate)
    except Exception:
        return ()
    if not isinstance(parsed, dict):
        return ()

    groups: list[tuple[str, tuple[PlanningTrackDefinition, ...]]] = []
    for group_key, raw_tracks in parsed.items():
        tracks: list[PlanningTrackDefinition] = []
        if isinstance(raw_tracks, list):
            for index, item in enumerate(raw_tracks):
                if isinstance(item, dict):
                    key = _clean(item.get("key"))
                    label = _clean(item.get("label"))
                else:
                    key = _clean(item)
                    label = _clean(item)
                if not key:
                    key = f"{group_key}-{index + 1}"
                if not label:
                    label = t(locale, f"offshore.work_menu.track.{group_key}")
                tracks.append(PlanningTrackDefinition(track_key=key, track_label=label, track_group=str(group_key)))
        if tracks:
            groups.append((str(group_key), tuple(tracks)))
    return tuple(groups)


def _publication_title(row: dict[str, object] | None) -> str | None:
    if not row:
        return None
    return _safe_title(row.get("composition_name") or row.get("unresolved_text"))


def _resolve_builder_composition_title(builder_flow, composition_id: str | None) -> tuple[str | None, tuple[PlanningComponentReference, ...]]:
    composition_id = _clean(composition_id)
    if not composition_id or builder_flow is None:
        return None, ()
    repository = getattr(builder_flow, "_composition_repository", None)
    if repository is None:
        return None, ()
    composition = repository.get(composition_id)
    if composition is None:
        return None, ()
    components = tuple(
        PlanningComponentReference(
            component_id=_clean(getattr(item, "component_id", None)),
            component_name=_safe_title(getattr(item, "component_name", None)) or _clean(getattr(item, "component_id", None)),
            role=_safe_title(getattr(item, "role", None)),
            sort_order=int(getattr(item, "sort_order", 0) or 0),
        )
        for item in getattr(composition, "components", ())
        if _clean(getattr(item, "component_id", None))
    )
    return _safe_title(getattr(composition, "composition_name", None)), components


def _normalize_builder_meal_slot(value: str) -> str:
    slot = _clean(value).lower()
    if not slot:
        return ""
    if slot.startswith("lunch"):
        return "lunch"
    if slot.startswith("dinner"):
        return "dinner"
    return slot


def _load_period(db, tenant_id: int, site_id: str) -> OffshoreWorkPeriod | None:
    settings = (
        db.query(OffshoreInstallationSettings)
        .filter(OffshoreInstallationSettings.tenant_id == int(tenant_id), OffshoreInstallationSettings.site_id == str(site_id))
        .first()
    )
    if settings is None:
        return None
    zone = _local_zone(site_timezone_name(tenant_id, site_id))
    today = datetime.now(zone).date()
    periods = (
        db.query(OffshoreWorkPeriod)
        .filter(OffshoreWorkPeriod.tenant_id == int(tenant_id), OffshoreWorkPeriod.site_id == str(site_id))
        .order_by(OffshoreWorkPeriod.starts_at.asc(), OffshoreWorkPeriod.id.asc())
        .all()
    )
    selected_start = _local_midnight(today, zone)
    selected_end = selected_start + timedelta(days=1)

    def _contains(period: OffshoreWorkPeriod) -> bool:
        return period.starts_at.astimezone(zone) < selected_end and period.ends_at.astimezone(zone) > selected_start

    active = [period for period in periods if _contains(period) and str(period.status).lower() == "active"]
    if active:
        return active[0]
    planned = [period for period in periods if _contains(period) and str(period.status).lower() == "planned"]
    if planned:
        return planned[0]
    upcoming = [period for period in periods if period.starts_at.astimezone(zone).date() > today and str(period.status).lower() != "cancelled"]
    if upcoming:
        return upcoming[0]
    return None


def _build_composition_options(builder_flow) -> tuple[PlanningCompositionOption, ...]:
    options: list[PlanningCompositionOption] = []
    if builder_flow is None:
        return ()
    try:
        for composition in builder_flow.list_compositions():
            composition_id = _clean(getattr(composition, "composition_id", None))
            if not composition_id:
                continue
            options.append(
                PlanningCompositionOption(
                    value=composition_id,
                    label=_safe_title(getattr(composition, "composition_name", None)) or composition_id,
                )
            )
    except Exception:
        return ()
    return tuple(sorted(options, key=lambda item: item.label))


class OffshoreEffectiveMenuService:
    def build_context(
        self,
        *,
        tenant_id: int | None,
        site_id: str | None,
        locale: str,
        work_period_id: int | None = None,
        service_event_ids: tuple[int, ...] | None = None,
    ) -> PlanningMenuContext:
        locale_value = normalize_locale(locale or "sv")
        now = datetime.now(UTC)

        if tenant_id is None or not site_id:
            return PlanningMenuContext(
                adapter_version=ADAPTER_VERSION,
                tenant_id=tenant_id,
                organization_id=tenant_id,
                tenant_name=None,
                installation_id=site_id,
                installation_name=None,
                work_period=None,
                period_start=None,
                period_end=None,
                generated_at=now,
            )

        db = get_session()
        try:
            _validate_scope(db, tenant_id, site_id)
            settings = (
                db.query(OffshoreInstallationSettings)
                .filter(OffshoreInstallationSettings.tenant_id == int(tenant_id), OffshoreInstallationSettings.site_id == str(site_id))
                .first()
            )
            tenant_name = None
            site_name = None
            if has_app_context():
                try:
                    row = db.execute(
                        __import__("sqlalchemy").text("SELECT name FROM tenants WHERE id = :id"),
                        {"id": int(tenant_id)},
                    ).fetchone()
                    tenant_name = str(row[0]) if row and row[0] else None
                    row = db.execute(
                        __import__("sqlalchemy").text("SELECT name FROM sites WHERE id = :id"),
                        {"id": str(site_id)},
                    ).fetchone()
                    site_name = str(row[0]) if row and row[0] else None
                except Exception:
                    tenant_name = tenant_name or None
                    site_name = site_name or None

            period = None
            if work_period_id is not None:
                period = (
                    db.query(OffshoreWorkPeriod)
                    .filter(
                        OffshoreWorkPeriod.tenant_id == int(tenant_id),
                        OffshoreWorkPeriod.site_id == str(site_id),
                        OffshoreWorkPeriod.id == int(work_period_id),
                    )
                    .first()
                )
            if period is None:
                period = _load_period(db, int(tenant_id), str(site_id))

            if period is None:
                return PlanningMenuContext(
                    adapter_version=ADAPTER_VERSION,
                    tenant_id=tenant_id,
                    organization_id=tenant_id,
                    tenant_name=tenant_name,
                    installation_id=site_id,
                    installation_name=site_name,
                    work_period=None,
                    period_start=None,
                    period_end=None,
                    generated_at=now,
                )

            zone = _local_zone(site_timezone_name(int(tenant_id), str(site_id)))
            track_groups = _parse_visibility_json(getattr(settings, "menu_track_visibility_json", None) if settings is not None else None, locale_value)
            builder_flow = None
            if has_app_context():
                from core.builder_menu_context_api import _get_menu_context_flow

                try:
                    builder_flow = _get_menu_context_flow()
                except Exception:
                    builder_flow = current_app.extensions.get("builder_menu_context_flow")
            composition_options = _build_composition_options(builder_flow)

            contexts = _menu_context_service.list_contexts_for_period(tenant_id=tenant_id, site_id=site_id, work_period_id=int(period.id))
            context_by_event_id = {int(row.service_event_id): row for row in contexts}
            event_filter = {int(item) for item in service_event_ids or ()}
            events = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.work_period_id == int(period.id),
                )
                .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                .all()
            )
            if event_filter:
                events = [event for event in events if int(event.id) in event_filter]

            decision_rows = (
                db.query(OffshoreWorkMenuDecision)
                .filter(
                    OffshoreWorkMenuDecision.tenant_id == int(tenant_id),
                    OffshoreWorkMenuDecision.site_id == str(site_id),
                    OffshoreWorkMenuDecision.service_event_id.in_([int(event.id) for event in events]),
                )
                .all()
            )
            decisions_by_event_and_track = {(int(row.service_event_id), str(row.menu_track_key)): row for row in decision_rows}

            menus_by_id: dict[str, str] = {}
            rows_by_menu_id: dict[str, list[dict[str, object]]] = {}
            if builder_flow is not None:
                try:
                    for menu in builder_flow.list_menus():
                        menu_id = _clean(getattr(menu, "menu_id", None))
                        if menu_id:
                            menus_by_id[menu_id] = _safe_title(getattr(menu, "title", None)) or menu_id
                except Exception:
                    menus_by_id = {}

            day_events: list[PlanningServiceEvent] = []
            context_warnings: list[str] = []
            for sequence_order, event in enumerate(events, start=1):
                local_date = event.starts_at.astimezone(zone).date()
                meal_slot = _resolve_service_slot(event)
                menu_context = context_by_event_id.get(int(event.id))
                builder_menu_id = _clean(getattr(menu_context, "builder_menu_id", None)) if menu_context is not None else ""
                if builder_menu_id and builder_menu_id not in rows_by_menu_id and builder_flow is not None:
                    try:
                        rows_by_menu_id[builder_menu_id] = list(builder_flow.list_menu_rows(builder_menu_id))
                    except Exception:
                        rows_by_menu_id[builder_menu_id] = []
                menu_rows = rows_by_menu_id.get(builder_menu_id, [])
                matching_rows = [
                    row
                    for row in menu_rows
                    if _clean(row.get("day")) == _weekday_key(local_date)
                    and _normalize_builder_meal_slot(str(row.get("meal_slot") or "")) == meal_slot
                ]
                ordered_tracks = [track for _, track_group in track_groups for track in track_group]
                meal_items: list[EffectivePlanningMenuItem] = []
                service_warnings: list[str] = []

                for index, track in enumerate(ordered_tracks):
                    published_row = matching_rows[index] if index < len(matching_rows) else None
                    published_title = _publication_title(published_row)
                    decision = decisions_by_event_and_track.get((int(event.id), track.track_key))
                    decision_type = _clean(getattr(decision, "decision_type", None)) or None
                    source_type = EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM
                    readiness = EffectiveMenuReadiness.UNRESOLVED
                    effective_title = published_title
                    display_name = published_title
                    component_refs: tuple[PlanningComponentReference, ...] = ()
                    builder_reference: PlanningCompositionReference | None = None
                    publication_reference = None
                    operational_reference = None
                    warnings: list[str] = []

                    if menu_context is not None:
                        publication_reference = PlanningPublicationReference(
                            publication_pin_id=_clean(getattr(menu_context, "builder_publication_pin_id", None)) or None,
                            builder_menu_id=_clean(getattr(menu_context, "builder_menu_id", None)) or None,
                            builder_menu_version=int(getattr(menu_context, "builder_menu_version", 0) or 0) or None,
                            publication_year=int(getattr(menu_context, "builder_publication_year", 0) or 0) or None,
                            publication_week=int(getattr(menu_context, "builder_publication_week", 0) or 0) or None,
                        )

                    if decision is not None:
                        operational_reference = PlanningOperationalDecisionReference(
                            decision_id=int(getattr(decision, "id", 0) or 0) or None,
                            decision_type=decision_type or "use_published",
                            source_publication_pin_id=_clean(getattr(decision, "source_publication_pin_id", None)) or None,
                            source_publication_year=int(getattr(decision, "source_publication_year", 0) or 0) or None,
                            source_publication_week=int(getattr(decision, "source_publication_week", 0) or 0) or None,
                            builder_composition_id=_clean(getattr(decision, "selected_builder_composition_id", None)) or None,
                            free_text=_safe_title(getattr(decision, "free_text", None)),
                        )
                        if decision_type == "use_builder_composition":
                            source_type = EffectiveMenuSourceType.OPERATIONAL_BUILDER_OVERRIDE
                            effective_title, component_refs = _resolve_builder_composition_title(builder_flow, getattr(decision, "selected_builder_composition_id", None))
                            builder_reference = None if not _clean(getattr(decision, "selected_builder_composition_id", None)) else PlanningCompositionReference(
                                composition_id=_clean(getattr(decision, "selected_builder_composition_id", None)),
                                composition_name=effective_title or _clean(getattr(decision, "selected_builder_composition_id", None)),
                            )
                            display_name = effective_title or published_title
                            if builder_reference is None:
                                warnings.append("missing_builder_composition")
                            if not component_refs:
                                warnings.append("composition_without_components")
                                readiness = EffectiveMenuReadiness.PARTIALLY_STRUCTURED if builder_reference is not None else EffectiveMenuReadiness.UNRESOLVED
                            else:
                                readiness = EffectiveMenuReadiness.STRUCTURED
                        elif decision_type == "use_free_text":
                            source_type = EffectiveMenuSourceType.OPERATIONAL_FREE_TEXT
                            effective_title = _safe_title(getattr(decision, "free_text", None))
                            display_name = effective_title
                            warnings.append("free_text_item")
                            readiness = EffectiveMenuReadiness.UNRESOLVED
                        else:
                            effective_title = published_title
                            display_name = published_title
                    else:
                        if published_title is None:
                            warnings.append("missing_publication_reference")
                        elif _clean(published_row.get("composition_id")):
                            effective_title, component_refs = _resolve_builder_composition_title(builder_flow, published_row.get("composition_id"))
                            builder_reference = PlanningCompositionReference(
                                composition_id=_clean(published_row.get("composition_id")),
                                composition_name=effective_title or _clean(published_row.get("composition_id")),
                            )
                            display_name = effective_title or published_title
                            source_type = EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM
                            if component_refs:
                                readiness = EffectiveMenuReadiness.STRUCTURED
                            else:
                                warnings.append("composition_without_components")
                                readiness = EffectiveMenuReadiness.PARTIALLY_STRUCTURED
                        else:
                            warnings.append("incomplete_structured_data")

                    if track.track_group not in {"primary", "secondary"}:
                        warnings.append("unknown_track")
                    if source_type == EffectiveMenuSourceType.OPERATIONAL_FREE_TEXT:
                        warnings.append("incomplete_structured_data")
                    if source_type == EffectiveMenuSourceType.OPERATIONAL_BUILDER_OVERRIDE and builder_reference is None:
                        warnings.append("incomplete_structured_data")
                    if source_type == EffectiveMenuSourceType.PUBLISHED_BUILDER_ITEM and publication_reference is None:
                        warnings.append("missing_publication_reference")

                    has_builder_composition = builder_reference is not None
                    has_components = len(component_refs) > 0
                    capabilities = build_capabilities(
                        has_builder_composition=has_builder_composition,
                        has_components=has_components,
                        readiness=readiness,
                    )

                    meal_items.append(
                        EffectivePlanningMenuItem(
                            stable_item_id=f"{tenant_id}:{site_id}:{event.id}:{track.track_key}",
                            tenant_id=int(tenant_id),
                            installation_id=str(site_id),
                            service_event_id=int(event.id),
                            service_date=local_date.isoformat(),
                            meal_slot=meal_slot,
                            service_label=_safe_title(getattr(event, "display_name", None)) or meal_slot,
                            track_key=track.track_key,
                            track_label=track.track_label,
                            track_group=track.track_group,
                            source_type=source_type,
                            readiness=readiness,
                            display_name=display_name,
                            published_title=published_title,
                            effective_title=effective_title,
                            published_reference=publication_reference,
                            operational_decision_reference=operational_reference,
                            builder_composition_reference=builder_reference,
                            component_references=component_refs,
                            capabilities=capabilities,
                            warnings=tuple(warnings),
                            decision_type=decision_type,
                            decision_label=t(locale_value, "offshore.work_menu.decision.use_published") if not decision_type else t(locale_value, f"offshore.work_menu.decision.{decision_type}"),
                            row_state=(decision_type or "published") if decision is not None else ("empty" if published_title is None else "published"),
                        )
                    )
                    service_warnings.extend(warnings)

                day_events.append(
                    PlanningServiceEvent(
                        service_event_id=int(event.id),
                        service_date=local_date.isoformat(),
                        meal_slot=meal_slot,
                        service_label=_safe_title(getattr(event, "display_name", None)) or meal_slot,
                        sequence_order=sequence_order,
                        local_time=event.starts_at.astimezone(zone).strftime("%H:%M"),
                        menu_context_status=_clean(getattr(menu_context, "resolution_status", None)) or t(locale_value, "offshore.work_menu.context_status.missing"),
                        menu_title=menus_by_id.get(builder_menu_id),
                        items=tuple(meal_items),
                    )
                )
                context_warnings.extend(service_warnings)

            work_period = PlanningWorkPeriodReference(
                id=int(period.id),
                name=str(period.name),
                status=str(period.status),
                starts_at=period.starts_at.astimezone(zone).isoformat(),
                ends_at=period.ends_at.astimezone(zone).isoformat(),
            )

            period_start = day_events[0].service_date if day_events else period.starts_at.astimezone(zone).date().isoformat()
            period_end = day_events[-1].service_date if day_events else period.ends_at.astimezone(zone).date().isoformat()

            return PlanningMenuContext(
                adapter_version=ADAPTER_VERSION,
                tenant_id=int(tenant_id),
                organization_id=int(tenant_id),
                tenant_name=tenant_name,
                installation_id=str(site_id),
                installation_name=site_name,
                work_period=work_period,
                period_start=period_start,
                period_end=period_end,
                generated_at=now,
                track_groups=track_groups,
                composition_options=composition_options,
                service_events=tuple(day_events),
                warnings=tuple(context_warnings),
            )
        finally:
            db.close()


_service = OffshoreEffectiveMenuService()
