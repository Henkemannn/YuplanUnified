from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, request, session
from sqlalchemy import text

from core.context import get_active_context
from core.db import get_new_session, get_session, get_site_tenant

from .i18n import copy_for, normalize_locale, t
from .models import OffshoreInstallationSettings, OffshoreMenuCycle, OffshoreMenuCycleSlot, OffshoreWorkPosition
from .navigation import NAV_ITEMS, ROADMAP_ITEMS

POSITION_TYPES = ("cook", "lead", "bakery", "other")
THEME_OPTIONS = ("system", "light", "dark")
LOCALE_OPTIONS = ("sv", "no", "en")


@dataclass(frozen=True)
class OffshoreContext:
    tenant_id: int | None
    site_id: str | None
    tenant_name: str | None
    site_name: str | None


def resolve_locale() -> str:
    requested = (request.args.get("lang") or session.get("offshore_locale") or "").strip().lower()
    return normalize_locale(requested)


def resolve_theme() -> str:
    theme = (session.get("offshore_theme") or "system").strip().lower()
    if theme not in THEME_OPTIONS:
        return "system"
    return theme


def _lookup_names(tenant_id: int | None, site_id: str | None) -> tuple[str | None, str | None]:
    tenant_name = None
    site_name = None
    db = get_session()
    try:
        if tenant_id is not None:
            row = db.execute(text("SELECT name FROM tenants WHERE id = :id"), {"id": int(tenant_id)}).fetchone()
            if row and row[0]:
                tenant_name = str(row[0])
        if site_id:
            row = db.execute(text("SELECT name FROM sites WHERE id = :id"), {"id": str(site_id)}).fetchone()
            if row and row[0]:
                site_name = str(row[0])
    finally:
        db.close()
    return tenant_name, site_name


def resolve_active_context() -> dict[str, object]:
    ctx = get_active_context()
    tenant_id = ctx.get("tenant_id")
    session_site_id = ctx.get("site_id")
    requested_site_id = (request.args.get("site_id") or "").strip() or None

    if not session_site_id:
        return {"redirect": True, "reason": "missing_site"}

    if requested_site_id and requested_site_id != session_site_id:
        return {"redirect": False, "forbidden": True, "reason": "site_mismatch"}

    db_site_tenant = None
    try:
        db_site_tenant = get_site_tenant(str(session_site_id))
    except Exception:
        db_site_tenant = None

    if tenant_id is not None and db_site_tenant is not None and int(db_site_tenant) != int(tenant_id):
        return {"redirect": False, "forbidden": True, "reason": "tenant_mismatch"}

    tenant_name, site_name = _lookup_names(tenant_id, session_site_id)
    return {
        "redirect": False,
        "forbidden": False,
        "tenant_id": tenant_id,
        "site_id": session_site_id,
        "tenant_name": tenant_name,
        "site_name": site_name,
    }


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "position"


def _validate_timezone(timezone: str) -> str:
    candidate = _clean(timezone)
    if not candidate:
        raise ValueError("offshore.validation.invalid_timezone")
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("offshore.validation.invalid_timezone") from exc
    return candidate


def _validate_locale(locale: str) -> str:
    candidate = _clean(locale).lower()
    if candidate not in LOCALE_OPTIONS:
        raise ValueError("offshore.validation.invalid_locale")
    return candidate


def _validate_theme(theme: str) -> str:
    candidate = _clean(theme).lower()
    if candidate not in THEME_OPTIONS:
        raise ValueError("offshore.validation.invalid_theme")
    return candidate


def _validate_portions(value: object | None) -> int | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        count = int(raw)
    except Exception as exc:
        raise ValueError("offshore.validation.invalid_portions") from exc
    if count < 1 or count > 10000:
        raise ValueError("offshore.validation.invalid_portions")
    return count


def _validate_name(value: object | None, key: str = "offshore.validation.name_required") -> str:
    name = _clean(value)
    if not name:
        raise ValueError(key)
    return name


def _validate_position_type(value: object | None) -> str:
    candidate = _clean(value).lower()
    if candidate not in POSITION_TYPES:
        raise ValueError("offshore.validation.invalid_position_type")
    return candidate


def _validate_cycle_length(value: object | None) -> int:
    raw = _clean(value)
    try:
        count = int(raw)
    except Exception as exc:
        raise ValueError("offshore.validation.invalid_cycle_length") from exc
    if count < 1 or count > 52:
        raise ValueError("offshore.validation.invalid_cycle_length")
    return count


class OffshoreService:
    def _site_tenant_id(self, db, site_id: str) -> int | None:
        if not site_id:
            return None
        row = db.execute(text("SELECT tenant_id FROM sites WHERE id = :sid"), {"sid": site_id}).fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])

    def _validate_scope(self, db, tenant_id: int | None, site_id: str | None) -> None:
        if tenant_id is None or not site_id:
            raise ValueError("offshore.validation.missing_context")
        site_tenant_id = self._site_tenant_id(db, site_id)
        if site_tenant_id is None or int(site_tenant_id) != int(tenant_id):
            raise LookupError("offshore.validation.cross_site")

    def _base_query(self, db, model, tenant_id: int, site_id: str):
        return db.query(model).filter(model.tenant_id == int(tenant_id), model.site_id == str(site_id))

    def _normalize_positions(self, db, tenant_id: int, site_id: str) -> None:
        rows = (
            self._base_query(db, OffshoreWorkPosition, tenant_id, site_id)
            .order_by(OffshoreWorkPosition.sort_order.asc(), OffshoreWorkPosition.id.asc())
            .all()
        )
        for index, row in enumerate(rows, start=1):
            row.sort_order = index
            row.updated_at = _now()

    def _ensure_unique_code(self, db, tenant_id: int, site_id: str, code: str, current_id: int | None = None) -> str:
        candidate = _clean(code) or "position"
        query = self._base_query(db, OffshoreWorkPosition, tenant_id, site_id).filter(OffshoreWorkPosition.code == candidate)
        if current_id is not None:
            query = query.filter(OffshoreWorkPosition.id != int(current_id))
        if query.first() is not None:
            raise ValueError("offshore.validation.duplicate_code")
        return candidate

    def get_context(self, tenant_id: int | None, site_id: str | None) -> OffshoreContext:
        return OffshoreContext(tenant_id=tenant_id, site_id=site_id, tenant_name=_lookup_names(tenant_id, site_id)[0], site_name=_lookup_names(tenant_id, site_id)[1])

    def load_state(self, tenant_id: int | None, site_id: str | None) -> dict[str, object]:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            settings = self._base_query(db, OffshoreInstallationSettings, int(tenant_id), str(site_id)).first()
            positions = (
                self._base_query(db, OffshoreWorkPosition, int(tenant_id), str(site_id))
                .order_by(OffshoreWorkPosition.sort_order.asc(), OffshoreWorkPosition.id.asc())
                .all()
            )
            cycles = (
                self._base_query(db, OffshoreMenuCycle, int(tenant_id), str(site_id))
                .order_by(OffshoreMenuCycle.is_active.desc(), OffshoreMenuCycle.id.desc())
                .all()
            )
            active_cycle = next((cycle for cycle in cycles if cycle.is_active), None)
            cycle_slots: dict[int, list[OffshoreMenuCycleSlot]] = {}
            for cycle in cycles:
                slots = (
                    self._base_query(db, OffshoreMenuCycleSlot, int(tenant_id), str(site_id))
                    .filter(OffshoreMenuCycleSlot.menu_cycle_id == cycle.id)
                    .order_by(OffshoreMenuCycleSlot.cycle_index.asc(), OffshoreMenuCycleSlot.sort_order.asc(), OffshoreMenuCycleSlot.id.asc())
                    .all()
                )
                cycle_slots[cycle.id] = slots
            return {
                "settings": settings,
                "positions": positions,
                "cycles": cycles,
                "active_cycle": active_cycle,
                "cycle_slots": cycle_slots,
            }
        finally:
            db.close()

    def save_installation_settings(self, *, tenant_id: int | None, site_id: str | None, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreInstallationSettings:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            timezone = _validate_timezone(payload.get("timezone"))
            default_locale = _validate_locale(payload.get("default_locale"))
            default_theme = _validate_theme(payload.get("default_theme"))
            default_portions = _validate_portions(payload.get("default_portions"))
            menu_track_visibility_json = _clean(payload.get("menu_track_visibility_json")) or None
            is_active = str(payload.get("is_active") or "").strip().lower() not in ("0", "false", "off", "no")
            row = self._base_query(db, OffshoreInstallationSettings, int(tenant_id), str(site_id)).first()
            if row is None:
                row = OffshoreInstallationSettings(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    timezone=timezone,
                    default_locale=default_locale,
                    default_theme=default_theme,
                    default_portions=default_portions,
                    menu_track_visibility_json=menu_track_visibility_json,
                    is_active=is_active,
                    created_by_user_id=actor_user_id,
                    updated_by_user_id=actor_user_id,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(row)
            else:
                row.timezone = timezone
                row.default_locale = default_locale
                row.default_theme = default_theme
                row.default_portions = default_portions
                row.menu_track_visibility_json = menu_track_visibility_json
                row.is_active = is_active
                row.updated_by_user_id = actor_user_id
                row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_work_position(self, *, tenant_id: int | None, site_id: str | None, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreWorkPosition:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            name = _validate_name(payload.get("name"))
            position_type = _validate_position_type(payload.get("position_type"))
            description = _clean(payload.get("description")) or None
            code_input = _clean(payload.get("code"))
            base_code = _slugify(code_input or name)
            code = self._ensure_unique_code(db, int(tenant_id), str(site_id), base_code)
            max_sort = db.query(OffshoreWorkPosition.sort_order).filter_by(tenant_id=int(tenant_id), site_id=str(site_id)).order_by(OffshoreWorkPosition.sort_order.desc()).first()
            next_sort = int(max_sort[0]) + 1 if max_sort and max_sort[0] is not None else 1
            row = OffshoreWorkPosition(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                code=code,
                name=name,
                description=description,
                position_type=position_type,
                sort_order=next_sort,
                is_active=True,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            db.commit()
            self._normalize_positions(db, int(tenant_id), str(site_id))
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_work_position(self, *, tenant_id: int | None, site_id: str | None, position_id: int, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreWorkPosition:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            row = self._base_query(db, OffshoreWorkPosition, int(tenant_id), str(site_id)).filter(OffshoreWorkPosition.id == int(position_id)).first()
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            row.name = _validate_name(payload.get("name"))
            row.position_type = _validate_position_type(payload.get("position_type"))
            row.description = _clean(payload.get("description")) or None
            row.updated_by_user_id = actor_user_id
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def toggle_work_position(self, *, tenant_id: int | None, site_id: str | None, position_id: int, actor_user_id: int | None) -> OffshoreWorkPosition:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            row = self._base_query(db, OffshoreWorkPosition, int(tenant_id), str(site_id)).filter(OffshoreWorkPosition.id == int(position_id)).first()
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            row.is_active = not bool(row.is_active)
            row.updated_by_user_id = actor_user_id
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def move_work_position(self, *, tenant_id: int | None, site_id: str | None, position_id: int, direction: str, actor_user_id: int | None) -> list[OffshoreWorkPosition]:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            rows = (
                self._base_query(db, OffshoreWorkPosition, int(tenant_id), str(site_id))
                .order_by(OffshoreWorkPosition.sort_order.asc(), OffshoreWorkPosition.id.asc())
                .all()
            )
            if not rows:
                return []
            index = next((i for i, row in enumerate(rows) if int(row.id) == int(position_id)), None)
            if index is None:
                raise LookupError("offshore.validation.cross_site")
            if direction == "up" and index > 0:
                rows[index - 1], rows[index] = rows[index], rows[index - 1]
            elif direction == "down" and index < len(rows) - 1:
                rows[index + 1], rows[index] = rows[index], rows[index + 1]
            else:
                return rows
            for sort_index, row in enumerate(rows, start=1):
                row.sort_order = sort_index
                row.updated_by_user_id = actor_user_id
                row.updated_at = _now()
            db.commit()
            for row in rows:
                db.refresh(row)
            return rows
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_menu_cycle(self, *, tenant_id: int | None, site_id: str | None, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreMenuCycle:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            name = _validate_name(payload.get("name"))
            description = _clean(payload.get("description")) or None
            cycle_length = _validate_cycle_length(payload.get("cycle_length"))
            is_active = str(payload.get("is_active") or "").strip().lower() not in ("0", "false", "off", "no")
            row = OffshoreMenuCycle(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                name=name,
                description=description,
                cycle_length=cycle_length,
                is_active=is_active,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
                created_at=_now(),
                updated_at=_now(),
            )
            if is_active:
                self._deactivate_other_cycles(db, int(tenant_id), str(site_id))
            db.add(row)
            db.flush()
            self._sync_cycle_slots(db, row, cycle_length)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_menu_cycle(self, *, tenant_id: int | None, site_id: str | None, cycle_id: int, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreMenuCycle:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            row = self._base_query(db, OffshoreMenuCycle, int(tenant_id), str(site_id)).filter(OffshoreMenuCycle.id == int(cycle_id)).first()
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            row.name = _validate_name(payload.get("name"))
            row.description = _clean(payload.get("description")) or None
            new_length = _validate_cycle_length(payload.get("cycle_length"))
            row.cycle_length = new_length
            row.updated_by_user_id = actor_user_id
            row.updated_at = _now()
            db.flush()
            self._sync_cycle_slots(db, row, new_length)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def toggle_menu_cycle(self, *, tenant_id: int | None, site_id: str | None, cycle_id: int, actor_user_id: int | None) -> OffshoreMenuCycle:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            row = self._base_query(db, OffshoreMenuCycle, int(tenant_id), str(site_id)).filter(OffshoreMenuCycle.id == int(cycle_id)).first()
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            new_state = not bool(row.is_active)
            if new_state:
                self._deactivate_other_cycles(db, int(tenant_id), str(site_id), exclude_cycle_id=int(cycle_id))
            row.is_active = new_state
            row.updated_by_user_id = actor_user_id
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_cycle_slot(self, *, tenant_id: int | None, site_id: str | None, cycle_id: int, slot_id: int, actor_user_id: int | None, payload: dict[str, object]) -> OffshoreMenuCycleSlot:
        db = get_new_session()
        try:
            self._validate_scope(db, tenant_id, site_id)
            row = self._base_query(db, OffshoreMenuCycleSlot, int(tenant_id), str(site_id)).filter(OffshoreMenuCycleSlot.id == int(slot_id)).first()
            if row is None:
                raise LookupError("offshore.validation.cross_site")
            if int(row.menu_cycle_id) != int(cycle_id):
                raise LookupError("offshore.validation.cross_site")
            row.label = _validate_name(payload.get("label"), key="offshore.validation.label_required")
            row.description = _clean(payload.get("description")) or None
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _deactivate_other_cycles(self, db, tenant_id: int, site_id: str, exclude_cycle_id: int | None = None) -> None:
        query = self._base_query(db, OffshoreMenuCycle, tenant_id, site_id).filter(OffshoreMenuCycle.is_active.is_(True))
        if exclude_cycle_id is not None:
            query = query.filter(OffshoreMenuCycle.id != int(exclude_cycle_id))
        for row in query.all():
            row.is_active = False
            row.updated_at = _now()

    def _sync_cycle_slots(self, db, cycle: OffshoreMenuCycle, cycle_length: int) -> None:
        slots = (
            self._base_query(db, OffshoreMenuCycleSlot, int(cycle.tenant_id), str(cycle.site_id))
            .filter(OffshoreMenuCycleSlot.menu_cycle_id == int(cycle.id))
            .order_by(OffshoreMenuCycleSlot.cycle_index.asc(), OffshoreMenuCycleSlot.id.asc())
            .all()
        )
        existing_by_index = {int(slot.cycle_index): slot for slot in slots}
        if len(existing_by_index) > cycle_length:
            for idx in sorted([index for index in existing_by_index if index > cycle_length], reverse=True):
                db.delete(existing_by_index[idx])
            slots = [slot for slot in slots if int(slot.cycle_index) <= cycle_length]
        for index in range(1, cycle_length + 1):
            slot = existing_by_index.get(index)
            if slot is None:
                slot = OffshoreMenuCycleSlot(
                    tenant_id=int(cycle.tenant_id),
                    site_id=str(cycle.site_id),
                    menu_cycle_id=int(cycle.id),
                    cycle_index=index,
                    label=f"Meny {index}",
                    description=None,
                    sort_order=index,
                    is_active=True,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(slot)
            else:
                slot.sort_order = index
                slot.is_active = True
                slot.updated_at = _now()


_service = OffshoreService()


def build_vm(*, locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    labels = copy_for(locale)
    return {
        "lang": locale,
        "theme": theme,
        "labels": labels,
        "nav_items": [{**item, "label": t(locale, item["label_key"])} for item in NAV_ITEMS],
        "tenant_id": tenant_id,
        "site_id": site_id,
        "tenant_name": tenant_name,
        "site_name": site_name,
        "user_name": session.get("full_name") or session.get("username") or session.get("user_email") or "Inloggad",
        "user_role": role,
        "can_manage": (role or "").strip().lower() in ("admin", "superuser"),
        "roadmap_items": [t(locale, key) for key in ROADMAP_ITEMS],
        "support_mail": "mailto:support@yuplan.se",
        "today": _date.today().isoformat(),
        "allow_site_switch": (role or "").strip().lower() in ("admin", "superuser"),
        "shell_brand": labels["offshore.brand"],
        "position_type_options": [{"value": key, "label": t(locale, f"offshore.position_type.{key}")} for key in POSITION_TYPES],
        "locale_options": [{"value": key, "label": t(locale, f"offshore.locale.{key}")} for key in LOCALE_OPTIONS],
        "theme_options": [{"value": key, "label": t(locale, f"offshore.theme.{key}")} for key in THEME_OPTIONS],
        "installation_default_timezone": "Europe/Oslo",
    }


def build_dashboard_vm(locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    vm = build_vm(
        locale=locale,
        theme=theme,
        role=role,
        tenant_id=tenant_id,
        site_id=site_id,
        tenant_name=tenant_name,
        site_name=site_name,
    )
    state = _service.load_state(tenant_id, site_id) if tenant_id is not None and site_id else {"settings": None, "positions": [], "cycles": [], "active_cycle": None, "cycle_slots": {}}
    settings = state["settings"]
    positions = state["positions"]
    cycles = state["cycles"]
    active_cycle = state["active_cycle"]
    active_slots = state["cycle_slots"].get(active_cycle.id, []) if active_cycle else []
    period_summary = None
    if tenant_id is not None and site_id:
        try:
            from .periods import period_dashboard_payload

            period_summary = period_dashboard_payload(tenant_id, site_id, locale=locale)
        except Exception:
            period_summary = None
    vm.update(
        {
            "page_title": vm["labels"]["offshore.dashboard.title"],
            "page_subtitle": vm["labels"]["offshore.dashboard.subtitle"],
            "empty_title": vm["labels"]["offshore.dashboard.no_active_period"],
            "empty_body": vm["labels"]["offshore.dashboard.no_active_period_body"],
            "today_placeholder": vm["labels"]["offshore.dashboard.today_placeholder"],
            "cta_label": vm["labels"]["offshore.dashboard.open_settings"],
            "roadmap_title": vm["labels"]["offshore.dashboard.roadmap"],
            "installation_status": vm["labels"]["offshore.dashboard.installation.configured"] if settings else vm["labels"]["offshore.dashboard.installation.not_configured"],
            "installation_timezone": getattr(settings, "timezone", None),
            "work_positions_status": vm["labels"]["offshore.dashboard.work_positions.active_count"].format(count=len([row for row in positions if row.is_active])),
            "menu_cycle_status": vm["labels"]["offshore.dashboard.menu_cycle.not_configured"],
            "menu_cycle_active_name": getattr(active_cycle, "name", None),
            "menu_cycle_slot_count": len(active_slots),
            "menu_cycle_active": bool(active_cycle and active_cycle.is_active),
            "active_work_positions": positions,
            "active_menu_cycle_slots": active_slots,
            "has_installation": bool(settings),
            "current_period": period_summary.get("current_period") if period_summary else None,
            "next_period": period_summary.get("next_period") if period_summary else None,
            "upcoming_service_events": int(period_summary.get("upcoming_event_count") or 0) if period_summary else 0,
            "has_period_templates": bool(period_summary.get("has_templates")) if period_summary else False,
            "period_overlap_warnings": period_summary.get("overlap_warnings") if period_summary else [],
        }
    )
    if active_cycle:
        vm["menu_cycle_status"] = vm["labels"]["offshore.dashboard.menu_cycle.configured"].format(name=active_cycle.name, count=len(active_slots))
    return vm


def build_settings_vm(locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    vm = build_vm(
        locale=locale,
        theme=theme,
        role=role,
        tenant_id=tenant_id,
        site_id=site_id,
        tenant_name=tenant_name,
        site_name=site_name,
    )
    state = _service.load_state(tenant_id, site_id) if tenant_id is not None and site_id else {"settings": None, "positions": [], "cycles": [], "active_cycle": None, "cycle_slots": {}}
    installation = state["settings"]
    positions = state["positions"]
    cycles = state["cycles"]
    active_cycle = state["active_cycle"]
    active_cycle_slots = state["cycle_slots"].get(active_cycle.id, []) if active_cycle else []
    vm.update(
        {
            "page_title": vm["labels"]["offshore.settings.title"],
            "page_subtitle": vm["labels"]["offshore.settings.subtitle"],
            "installation": installation,
            "installation_onboarding": installation is None,
            "positions": positions,
            "cycles": cycles,
            "active_cycle": active_cycle,
            "active_cycle_slots": active_cycle_slots,
            "is_manager": (role or "").strip().lower() in ("admin", "superuser"),
            "default_timezone": getattr(installation, "timezone", None) or "Europe/Oslo",
            "default_locale": getattr(installation, "default_locale", None) or "sv",
            "default_theme": getattr(installation, "default_theme", None) or "system",
            "default_portions": getattr(installation, "default_portions", None),
            "installation_status_label": vm["labels"]["offshore.settings.installation.configured"] if installation else vm["labels"]["offshore.settings.installation.not_configured"],
            "position_status_label": vm["labels"]["offshore.settings.positions.active_count"].format(count=len([row for row in positions if row.is_active])),
            "cycle_status_label": vm["labels"]["offshore.settings.menu_cycle.not_configured"],
            "cycle_count": len(cycles),
        }
    )
    if active_cycle:
        vm["cycle_status_label"] = vm["labels"]["offshore.settings.menu_cycle.configured"].format(name=active_cycle.name, count=len(active_cycle_slots))
    return vm
