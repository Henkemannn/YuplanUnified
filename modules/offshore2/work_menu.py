from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context, request, url_for

from core.db import get_session

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
    meals: tuple[OffshoreWorkMenuMealView, ...] = ()


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
        vm: dict[str, object] = {
            "lang": locale,
            "theme": theme,
            "labels": labels,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "tenant_name": tenant_name,
            "site_name": site_name,
            "user_name": request.headers.get("X-User-Name") or request.headers.get("X-Username") or "Inloggad",
            "user_role": role,
            "allow_site_switch": (role or "").strip().lower() in ("admin", "superuser"),
            "page_title": labels["offshore.work_menu.title"],
            "page_subtitle": labels["offshore.work_menu.subtitle"],
            "nav_items": [{**item, "label": t(locale, item["label_key"])} for item in NAV_ITEMS],
            "work_period": None,
            "days": (),
            "track_groups": (),
            "track_visibility": {},
            "has_menu": False,
            "is_managed_role": (role or "").strip().lower() in ("admin", "superuser", "cook", "editor"),
            "empty_title": labels["offshore.work_menu.empty_title"],
            "empty_body": labels["offshore.work_menu.empty_body"],
        }

        if tenant_id is None or not site_id:
            return vm

        db = get_session()
        try:
            period = self._load_period(db, int(tenant_id), str(site_id))
            if period is None:
                return vm

            settings = (
                db.query(OffshoreInstallationSettings)
                .filter(OffshoreInstallationSettings.tenant_id == int(tenant_id), OffshoreInstallationSettings.site_id == str(site_id))
                .first()
            )
            context_by_event_id = self._load_contexts(db, int(tenant_id), str(site_id), int(period.id))
            service_events = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.work_period_id == int(period.id),
                )
                .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                .all()
            )
            if not service_events:
                vm.update({"work_period": period, "empty_title": labels["offshore.work_menu.no_services_title"], "empty_body": labels["offshore.work_menu.no_services_body"]})
                return vm

            visibility = _parse_visibility_json(getattr(settings, "menu_track_visibility_json", None) if settings is not None else None, locale)
            all_tracks = tuple((str(group_key), tuple(tracks)) for group_key, tracks in visibility.items())

            builder_flow = current_app.extensions.get("builder_menu_context_flow") if has_app_context() else None
            menus_by_id: dict[str, str] = {}
            rows_by_menu_id: dict[str, list[dict[str, object]]] = {}
            composition_options: list[dict[str, str]] = []
            if builder_flow is not None:
                try:
                    for menu in builder_flow.list_menus():
                        menu_id = _clean(getattr(menu, "menu_id", None))
                        if menu_id:
                            menus_by_id[menu_id] = _safe_title(getattr(menu, "title", None)) or menu_id
                except Exception:
                    menus_by_id = {}
                try:
                    for composition in builder_flow.list_compositions():
                        composition_id = _clean(getattr(composition, "composition_id", None))
                        if not composition_id:
                            continue
                        composition_options.append(
                            {
                                "value": composition_id,
                                "label": _safe_title(getattr(composition, "composition_name", None)) or composition_id,
                            }
                        )
                except Exception:
                    composition_options = []

            decision_rows = (
                db.query(OffshoreWorkMenuDecision)
                .filter(
                    OffshoreWorkMenuDecision.tenant_id == int(tenant_id),
                    OffshoreWorkMenuDecision.site_id == str(site_id),
                    OffshoreWorkMenuDecision.service_event_id.in_([int(event.id) for event in service_events]),
                )
                .all()
            )
            decisions_by_event_and_track = {(int(row.service_event_id), str(row.menu_track_key)): row for row in decision_rows}

            day_map: dict[str, list[OffshoreWorkMenuMealView]] = {}
            day_order: list[str] = []
            zone = _local_zone(site_timezone_name(int(tenant_id), str(site_id)))

            for event in service_events:
                local_date = event.starts_at.astimezone(zone).date()
                day_key = _weekday_key(local_date)
                meal_slot = _resolve_service_slot(event)
                event_context = context_by_event_id.get(int(event.id))
                builder_menu_id = _clean(getattr(event_context, "builder_menu_id", None)) if event_context is not None else ""
                if builder_menu_id and builder_menu_id not in rows_by_menu_id and builder_flow is not None:
                    rows_by_menu_id[builder_menu_id] = self._load_menu_rows(builder_flow, builder_menu_id)
                menu_rows = rows_by_menu_id.get(builder_menu_id, [])
                matching_rows = [row for row in menu_rows if _clean(row.get("day")) == day_key and _clean(row.get("meal_slot")) == meal_slot]
                meal_label = labels[f"offshore.work_menu.meal_slot.{meal_slot}"]
                service_label = _safe_title(getattr(event, "display_name", None)) or meal_label
                menu_title = menus_by_id.get(builder_menu_id)
                meal_tracks: list[OffshoreWorkMenuTrackView] = []

                ordered_tracks = [track for group_key, track_group in all_tracks for track in track_group]
                for index, track in enumerate(ordered_tracks):
                    published_row = matching_rows[index] if index < len(matching_rows) else None
                    published_title = _publication_title(published_row)
                    decision = decisions_by_event_and_track.get((int(event.id), track["key"]))
                    decision_type = _clean(getattr(decision, "decision_type", None)) or None
                    effective_source_label = labels["offshore.work_menu.source.published"]
                    effective_title = published_title
                    row_state = "published"
                    if decision is not None:
                        effective_source_label = _decision_label(locale, decision_type or "use_published")
                        row_state = decision_type or "use_published"
                        if decision_type == "use_builder_composition":
                            effective_title = _resolve_builder_composition_title(builder_flow, getattr(decision, "selected_builder_composition_id", None)) or published_title
                        elif decision_type == "use_free_text":
                            effective_title = _safe_title(getattr(decision, "free_text", None)) or published_title
                        else:
                            effective_title = published_title
                    elif published_title is None:
                        effective_source_label = labels["offshore.work_menu.source.empty"]
                        row_state = "empty"

                    meal_tracks.append(
                        OffshoreWorkMenuTrackView(
                            track_key=track["key"],
                            track_label=track["label"],
                            track_group=str(track.get("group") or "primary"),
                            published_title=published_title,
                            effective_title=effective_title,
                            effective_source_label=effective_source_label,
                            decision_type=decision_type,
                            decision_label=_decision_label(locale, decision_type) if decision_type else None,
                            builder_composition_id=_clean(getattr(decision, "selected_builder_composition_id", None)) or None,
                            free_text=_safe_title(getattr(decision, "free_text", None)),
                            row_state=row_state,
                        )
                    )

                meal_vm = OffshoreWorkMenuMealView(
                    service_event_id=int(event.id),
                    meal_slot=meal_slot,
                    meal_label=meal_label,
                    local_time=event.starts_at.astimezone(zone).strftime("%H:%M"),
                    service_label=service_label,
                    menu_context_status=_clean(getattr(event_context, "resolution_status", None)) or labels["offshore.work_menu.context_status.missing"],
                    menu_title=menu_title,
                    tracks=tuple(meal_tracks),
                )
                day_map.setdefault(day_key, [])
                if day_key not in day_order:
                    day_order.append(day_key)
                day_map[day_key].append(meal_vm)

            days: list[OffshoreWorkMenuDayView] = []
            for day_key in day_order:
                meals = tuple(sorted(day_map.get(day_key, []), key=lambda meal: (meal.meal_slot, meal.local_time, meal.service_event_id)))
                first_event = next((event for event in service_events if _weekday_key(event.starts_at.astimezone(zone).date()) == day_key), None)
                local_date = first_event.starts_at.astimezone(zone).date().isoformat() if first_event is not None else day_key
                label = t(locale, f"offshore.weekday.{_date.fromisoformat(local_date).weekday()}") if first_event is not None else day_key.title()
                days.append(OffshoreWorkMenuDayView(local_date=local_date, label=label, meals=meals))

            vm.update(
                {
                    "work_period": period,
                    "days": tuple(days),
                    "track_groups": all_tracks,
                    "track_visibility": visibility,
                    "composition_options": tuple(sorted(composition_options, key=lambda row: row["label"])),
                    "has_menu": True,
                    "empty_title": labels["offshore.work_menu.title"],
                    "empty_body": labels["offshore.work_menu.subtitle"],
                }
            )
            return vm
        finally:
            db.close()

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


_service = OffshoreWorkMenuService()