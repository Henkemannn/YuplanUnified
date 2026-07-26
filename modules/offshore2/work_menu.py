from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context, request, url_for

from core.db import get_session

from .effective_menu import _service as _effective_menu_service
from .i18n import copy_for, t
from .navigation import NAV_ITEMS
from .menu_context import _service as _menu_context_service
from .models import (
    OffshoreInstallationSettings,
    OffshoreServiceEvent,
    OffshoreWorkMenuDecision,
    OffshoreWorkPeriod,
)
from .periods import _local_zone, site_timezone_name


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _safe_url(endpoint: str, **values: object) -> str:
    if has_app_context() and request is not None:
        try:
            return url_for(endpoint, **values)
        except Exception:
            pass
    if endpoint == "offshore2.work_menu":
        return "/offshore/work-menu"
    return "/offshore"


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


def _parse_visibility_json(raw_value: str | None, locale: str) -> dict[str, tuple[dict[str, str], ...]]:
    candidate = _clean(raw_value)
    if not candidate:
        return {}
    try:
        parsed = json.loads(candidate)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}

    groups: dict[str, tuple[dict[str, str], ...]] = {}
    for group_key, raw_tracks in parsed.items():
        tracks: list[dict[str, str]] = []
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
                tracks.append({"key": key, "label": label, "group": group_key})
        if tracks:
            groups[str(group_key)] = tuple(tracks)
    return groups


def _default_visible_track_keys(track_groups: tuple[tuple[str, tuple[object, ...]], ...]) -> tuple[str, ...]:
    primary_keys: list[str] = []
    fallback_keys: list[str] = []
    for group_key, tracks in track_groups:
        for track in tracks:
            track_key = _clean(getattr(track, "track_key", None))
            if not track_key:
                continue
            fallback_keys.append(track_key)
            if str(group_key) == "primary":
                primary_keys.append(track_key)
    chosen = primary_keys or fallback_keys[:2]
    return tuple(dict.fromkeys(chosen))


def _publication_title(row: dict[str, object] | None) -> str | None:
    if not row:
        return None
    return _safe_title(row.get("composition_name") or row.get("unresolved_text"))


def _decision_label(locale: str, decision_type: str) -> str:
    key = {
        "use_published": "offshore.work_menu.decision.use_published",
        "use_builder_composition": "offshore.work_menu.decision.use_builder_composition",
        "use_free_text": "offshore.work_menu.decision.use_free_text",
    }.get(decision_type, "offshore.work_menu.decision.use_published")
    return t(locale, key)


def _resolve_builder_composition_title(builder_flow, composition_id: str | None) -> str | None:
    composition_id = _clean(composition_id)
    if not composition_id or builder_flow is None:
        return None
    repository = getattr(builder_flow, "_composition_repository", None)
    if repository is None:
        return None
    composition = repository.get(composition_id)
    if composition is None:
        return None
    return _safe_title(getattr(composition, "composition_name", None))


@dataclass(frozen=True, slots=True)
class OffshoreWorkMenuTrackView:
    track_key: str
    track_label: str
    track_group: str
    published_title: str | None
    effective_title: str | None
    effective_source_label: str
    decision_type: str | None
    decision_label: str | None
    builder_composition_id: str | None
    free_text: str | None
    row_state: str


@dataclass(frozen=True, slots=True)
class OffshoreWorkMenuMealView:
    service_event_id: int
    meal_slot: str
    meal_label: str
    local_time: str
    service_label: str
    menu_context_status: str
    menu_title: str | None
    tracks: tuple[OffshoreWorkMenuTrackView, ...] = ()


@dataclass(frozen=True, slots=True)
class OffshoreWorkMenuDayView:
    local_date: str
    label: str
    is_today: bool = False
    meals: tuple[OffshoreWorkMenuMealView, ...] = ()


def _build_work_menu_view_model_from_context(*, context, labels: dict[str, str], locale: str, theme: str, role: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    default_visible_track_keys = _default_visible_track_keys(context.track_groups)
    vm: dict[str, object] = {
        "lang": locale,
        "theme": theme,
        "labels": labels,
        "tenant_id": context.tenant_id,
        "site_id": context.installation_id,
        "tenant_name": tenant_name,
        "site_name": site_name,
        "user_name": request.headers.get("X-User-Name") or request.headers.get("X-Username") or "Inloggad",
        "user_role": role,
        "allow_site_switch": (role or "").strip().lower() in ("admin", "superuser"),
        "page_title": labels["offshore.work_menu.title"],
        "page_subtitle": labels["offshore.work_menu.subtitle"],
        "nav_items": [{**item, "label": t(locale, item["label_key"])} for item in NAV_ITEMS],
        "work_period": context.work_period,
        "days": (),
        "track_groups": context.track_groups,
        "default_visible_track_keys": default_visible_track_keys,
        "track_visibility_storage_key": f"offshore.work_menu.visible_tracks:{context.tenant_id or tenant_name or 'tenant'}:{context.installation_id or site_name or 'site'}",
        "track_visibility": {},
        "has_menu": bool(context.service_events),
        "is_managed_role": (role or "").strip().lower() in ("admin", "superuser", "cook", "editor"),
        "empty_title": labels["offshore.work_menu.empty_title"],
        "empty_body": labels["offshore.work_menu.empty_body"],
        "composition_options": tuple({"value": option.value, "label": option.label} for option in context.composition_options),
    }

    if not context.service_events:
        if context.work_period is not None:
            vm.update({"empty_title": labels["offshore.work_menu.no_services_title"], "empty_body": labels["offshore.work_menu.no_services_body"]})
        return vm

    meal_slot_order = {"lunch": 0, "dinner": 1}
    day_map: dict[str, list[OffshoreWorkMenuMealView]] = {}
    day_order: list[str] = []
    try:
        zone = _local_zone(site_timezone_name(int(context.tenant_id), str(context.installation_id)))
        today = datetime.now(zone).date()
    except Exception:
        today = None
    for event in context.service_events:
        day_key = event.service_date
        if day_key not in day_map:
            day_map[day_key] = []
            day_order.append(day_key)
        meal_tracks: list[OffshoreWorkMenuTrackView] = []
        for item in event.items:
            if item.row_state == "empty":
                effective_source_label = labels["offshore.work_menu.source.empty"]
            elif item.source_type.value == "published_builder_item":
                effective_source_label = labels["offshore.work_menu.source.published"]
            elif item.source_type.value == "operational_builder_override":
                effective_source_label = item.decision_label or labels["offshore.work_menu.decision.use_builder_composition"]
            else:
                effective_source_label = item.decision_label or labels["offshore.work_menu.decision.use_free_text"]
            meal_tracks.append(
                OffshoreWorkMenuTrackView(
                    track_key=item.track_key,
                    track_label=item.track_label,
                    track_group=item.track_group,
                    published_title=item.published_title,
                    effective_title=item.effective_title,
                    effective_source_label=effective_source_label,
                    decision_type=item.decision_type,
                    decision_label=item.decision_label,
                    builder_composition_id=(item.operational_decision_reference.builder_composition_id if item.operational_decision_reference is not None else None),
                    free_text=(item.operational_decision_reference.free_text if item.operational_decision_reference is not None else None),
                    row_state=item.row_state,
                )
            )
        day_map[day_key].append(
            OffshoreWorkMenuMealView(
                service_event_id=event.service_event_id,
                meal_slot=event.meal_slot,
                meal_label=labels[f"offshore.work_menu.meal_slot.{event.meal_slot}"],
                local_time=event.local_time,
                service_label=event.service_label,
                menu_context_status=event.menu_context_status,
                menu_title=event.menu_title,
                tracks=tuple(meal_tracks),
            )
        )

    days: list[OffshoreWorkMenuDayView] = []
    for day_key in day_order:
        meals = tuple(sorted(day_map.get(day_key, []), key=lambda meal: (meal_slot_order.get(meal.meal_slot, 99), meal.local_time, meal.service_event_id)))
        try:
            local_date = _date.fromisoformat(day_key)
            label = t(locale, f"offshore.weekday.{local_date.weekday()}")
        except Exception:
            label = day_key.title()
        days.append(OffshoreWorkMenuDayView(local_date=day_key, label=label, is_today=bool(today and local_date == today), meals=meals))

    vm["days"] = tuple(days)
    return vm


class OffshoreWorkMenuService:
    def _load_period(self, db, tenant_id: int, site_id: str) -> OffshoreWorkPeriod | None:
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

    def _load_contexts(self, db, tenant_id: int, site_id: str, work_period_id: int) -> dict[int, object]:
        contexts = _menu_context_service.list_contexts_for_period(tenant_id=tenant_id, site_id=site_id, work_period_id=work_period_id)
        return {int(row.service_event_id): row for row in contexts}

    def _load_menu_rows(self, builder_flow, menu_id: str) -> list[dict[str, object]]:
        try:
            return list(builder_flow.list_menu_rows(menu_id))
        except Exception:
            return []

    def build_view_model(self, *, tenant_id: int | None, site_id: str | None, locale: str, theme: str, role: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
        labels = copy_for(locale)
        context = _effective_menu_service.build_context(
            tenant_id=tenant_id,
            site_id=site_id,
            locale=locale,
        )
        return _build_work_menu_view_model_from_context(
            context=context,
            labels=labels,
            locale=locale,
            theme=theme,
            role=role,
            tenant_name=tenant_name,
            site_name=site_name,
        )

    def save_decision(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, service_event_id: int, menu_track_key: str, decision_type: str, selected_builder_composition_id: str | None, free_text: str | None, actor_user_id: int | None = None) -> OffshoreWorkMenuDecision:
        db = get_session()
        try:
            if tenant_id is None or not site_id:
                raise ValueError("offshore.validation.missing_context")
            event = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.work_period_id == int(work_period_id),
                    OffshoreServiceEvent.id == int(service_event_id),
                )
                .first()
            )
            if event is None:
                raise LookupError("offshore.validation.cross_site")
            context = _menu_context_service.get_context_for_event(
                tenant_id=tenant_id,
                site_id=site_id,
                work_period_id=work_period_id,
                service_event_id=service_event_id,
            )
            if context is None:
                context = _menu_context_service.sync_service_event_context(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    work_period_id=work_period_id,
                    service_event_id=service_event_id,
                    db=db,
                )
            track_key = _clean(menu_track_key)
            decision_key = _clean(decision_type).lower()
            if decision_key not in {"use_published", "use_builder_composition", "use_free_text"}:
                raise ValueError("offshore.validation.invalid_decision_type")
            composition_id = _clean(selected_builder_composition_id)
            text_value = _clean(free_text)
            if decision_key == "use_builder_composition" and not composition_id:
                raise ValueError("offshore.validation.invalid_builder_composition")
            if decision_key == "use_free_text" and not text_value:
                raise ValueError("offshore.validation.free_text_required")
            if decision_key == "use_published" and (composition_id or text_value):
                raise ValueError("offshore.validation.invalid_decision_payload")
            if decision_key == "use_builder_composition" and text_value:
                raise ValueError("offshore.validation.invalid_decision_payload")
            if decision_key == "use_free_text" and composition_id:
                raise ValueError("offshore.validation.invalid_decision_payload")

            if decision_key == "use_builder_composition":
                builder_flow = current_app.extensions.get("builder_menu_context_flow") if has_app_context() else None
                composition = None
                if builder_flow is not None:
                    repository = getattr(builder_flow, "_composition_repository", None)
                    if repository is not None:
                        composition = repository.get(composition_id)
                if composition is None:
                    raise LookupError("offshore.validation.cross_site")

            existing = (
                db.query(OffshoreWorkMenuDecision)
                .filter(
                    OffshoreWorkMenuDecision.tenant_id == int(tenant_id),
                    OffshoreWorkMenuDecision.site_id == str(site_id),
                    OffshoreWorkMenuDecision.service_event_id == int(service_event_id),
                    OffshoreWorkMenuDecision.menu_track_key == track_key,
                )
                .first()
            )
            if existing is None:
                existing = OffshoreWorkMenuDecision(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    service_event_id=int(service_event_id),
                    menu_track_key=track_key,
                    decision_type=decision_key,
                    selected_builder_composition_id=composition_id or None,
                    free_text=text_value or None,
                    source_publication_pin_id=_clean(getattr(context, "builder_publication_pin_id", None)) or None,
                    source_publication_year=int(getattr(context, "builder_publication_year", 0) or 0),
                    source_publication_week=int(getattr(context, "builder_publication_week", 0) or 0),
                    created_by_user_id=actor_user_id,
                    updated_by_user_id=actor_user_id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(existing)
            else:
                existing.decision_type = decision_key
                existing.selected_builder_composition_id = composition_id or None
                existing.free_text = text_value or None
                existing.source_publication_pin_id = _clean(getattr(context, "builder_publication_pin_id", None)) or None
                existing.source_publication_year = int(getattr(context, "builder_publication_year", 0) or 0)
                existing.source_publication_week = int(getattr(context, "builder_publication_week", 0) or 0)
                existing.updated_by_user_id = actor_user_id
                existing.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(existing)
            return existing
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def reset_decision(self, *, tenant_id: int | None, site_id: str | None, work_period_id: int, service_event_id: int, menu_track_key: str, actor_user_id: int | None = None) -> bool:
        db = get_session()
        try:
            if tenant_id is None or not site_id:
                raise ValueError("offshore.validation.missing_context")
            event = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.work_period_id == int(work_period_id),
                    OffshoreServiceEvent.id == int(service_event_id),
                )
                .first()
            )
            if event is None:
                raise LookupError("offshore.validation.cross_site")
            track_key = _clean(menu_track_key)
            existing = (
                db.query(OffshoreWorkMenuDecision)
                .filter(
                    OffshoreWorkMenuDecision.tenant_id == int(tenant_id),
                    OffshoreWorkMenuDecision.site_id == str(site_id),
                    OffshoreWorkMenuDecision.service_event_id == int(service_event_id),
                    OffshoreWorkMenuDecision.menu_track_key == track_key,
                )
                .first()
            )
            if existing is None:
                return False
            db.delete(existing)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


_service = OffshoreWorkMenuService()