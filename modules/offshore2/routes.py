from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from core.auth import require_roles
from core.http_errors import forbidden, not_found

from .i18n import copy_for, normalize_locale
from .permissions import FEATURE_FLAG, VIEWER_ROLES, MANAGER_ROLES, gate_or_404
from .periods import (
    PERIOD_TEMPLATE_EVENT_STATUSES,
    WORK_PERIOD_STATUSES,
    period_dashboard_payload,
    serialize_template_event,
    serialize_period,
    serialize_service_event,
    serialize_template,
    site_timezone_name,
    _service as _period_service,
)
from .menu_context import _service as _menu_context_service
from .services import (
    _service,
    build_dashboard_vm,
    build_settings_vm,
    resolve_active_context,
    resolve_locale,
    resolve_theme,
)

bp = Blueprint("offshore2", __name__, url_prefix="/offshore")


@bp.before_request
def _gate_module():
    maybe = gate_or_404()
    if maybe is not None:
        return maybe
    return None


def _context_or_redirect():
    result = resolve_active_context()
    if result.get("redirect"):
        return redirect(url_for("ui.select_site", next=request.path))
    if result.get("forbidden"):
        return forbidden(str(result.get("reason") or "forbidden"), problem_type="https://example.com/problems/offshore-site-mismatch")
    return result


def _settings_redirect():
    lang = (request.args.get("lang") or "").strip()
    if lang:
        return redirect(url_for("offshore2.settings", lang=lang))
    return redirect(url_for("offshore2.settings"))


def _get_actor_user_id() -> int | None:
    user_id = request.headers.get("X-User-Id")
    if isinstance(user_id, str) and user_id.isdigit():
        return int(user_id)
    return None


def _flash_success(message_key: str) -> None:
    flash(message_key, "success")


def _flash_error(message_key: str) -> None:
    flash(message_key, "error")


def _handle_validation_error(exc: Exception):
    _flash_error(str(exc) or "offshore.validation.error")
    return _settings_redirect()


def _render_settings_vm(result: dict[str, object]):
    locale = resolve_locale()
    theme = resolve_theme()
    role = request.headers.get("X-User-Role") or None
    return build_settings_vm(
        locale=locale,
        theme=theme,
        role=role,
        tenant_id=result.get("tenant_id"),
        site_id=result.get("site_id"),
        tenant_name=result.get("tenant_name"),
        site_name=result.get("site_name"),
    )


@bp.get("")
@bp.get("/")
@require_roles(*VIEWER_ROLES)
def dashboard():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    locale = resolve_locale()
    theme = resolve_theme()
    vm = build_dashboard_vm(
        locale=locale,
        theme=theme,
        role=current_app.config.get("_offshore_role") or request.headers.get("X-User-Role") or None,
        tenant_id=result.get("tenant_id"),
        site_id=result.get("site_id"),
        tenant_name=result.get("tenant_name"),
        site_name=result.get("site_name"),
    )
    return render_template("offshore2/dashboard.html", vm=vm)


@bp.get("/settings")
@require_roles(*MANAGER_ROLES)
def settings():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    vm = _render_settings_vm(result)
    return render_template("offshore2/settings.html", vm=vm)


@bp.post("/settings/installation")
@require_roles(*MANAGER_ROLES)
def save_installation_settings():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.save_installation_settings(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            actor_user_id=_get_actor_user_id(),
            payload={
                "timezone": request.form.get("timezone"),
                "default_locale": request.form.get("default_locale"),
                "default_theme": request.form.get("default_theme"),
                "default_portions": request.form.get("default_portions"),
                "is_active": request.form.get("is_active"),
            },
        )
        _flash_success("offshore.success.installation_saved")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/work-positions")
@require_roles(*MANAGER_ROLES)
def create_work_position():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.create_work_position(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            actor_user_id=_get_actor_user_id(),
            payload={
                "name": request.form.get("name"),
                "position_type": request.form.get("position_type"),
                "code": request.form.get("code"),
                "description": request.form.get("description"),
            },
        )
        _flash_success("offshore.success.work_position_created")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/work-positions/<int:position_id>/update")
@require_roles(*MANAGER_ROLES)
def update_work_position(position_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.update_work_position(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            position_id=position_id,
            actor_user_id=_get_actor_user_id(),
            payload={
                "name": request.form.get("name"),
                "position_type": request.form.get("position_type"),
                "description": request.form.get("description"),
            },
        )
        _flash_success("offshore.success.work_position_saved")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/work-positions/<int:position_id>/toggle")
@require_roles(*MANAGER_ROLES)
def toggle_work_position(position_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        row = _service.toggle_work_position(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            position_id=position_id,
            actor_user_id=_get_actor_user_id(),
        )
        key = "offshore.success.work_position_activated" if row.is_active else "offshore.success.work_position_deactivated"
        _flash_success(key)
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/work-positions/<int:position_id>/move-up")
@require_roles(*MANAGER_ROLES)
def move_work_position_up(position_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.move_work_position(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            position_id=position_id,
            direction="up",
            actor_user_id=_get_actor_user_id(),
        )
        _flash_success("offshore.success.work_position_moved_up")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/work-positions/<int:position_id>/move-down")
@require_roles(*MANAGER_ROLES)
def move_work_position_down(position_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.move_work_position(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            position_id=position_id,
            direction="down",
            actor_user_id=_get_actor_user_id(),
        )
        _flash_success("offshore.success.work_position_moved_down")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/menu-cycle")
@require_roles(*MANAGER_ROLES)
def create_menu_cycle():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.create_menu_cycle(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            actor_user_id=_get_actor_user_id(),
            payload={
                "name": request.form.get("name"),
                "description": request.form.get("description"),
                "cycle_length": request.form.get("cycle_length"),
                "is_active": request.form.get("is_active"),
            },
        )
        _flash_success("offshore.success.menu_cycle_created")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/menu-cycle/<int:cycle_id>/update")
@require_roles(*MANAGER_ROLES)
def update_menu_cycle(cycle_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.update_menu_cycle(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            cycle_id=cycle_id,
            actor_user_id=_get_actor_user_id(),
            payload={
                "name": request.form.get("name"),
                "description": request.form.get("description"),
                "cycle_length": request.form.get("cycle_length"),
            },
        )
        _flash_success("offshore.success.menu_cycle_saved")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/menu-cycle/<int:cycle_id>/toggle")
@require_roles(*MANAGER_ROLES)
def toggle_menu_cycle(cycle_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        row = _service.toggle_menu_cycle(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            cycle_id=cycle_id,
            actor_user_id=_get_actor_user_id(),
        )
        key = "offshore.success.menu_cycle_activated" if row.is_active else "offshore.success.menu_cycle_deactivated"
        _flash_success(key)
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


@bp.post("/settings/menu-cycle/<int:cycle_id>/slots/<int:slot_id>/update")
@require_roles(*MANAGER_ROLES)
def update_menu_cycle_slot(cycle_id: int, slot_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _service.update_cycle_slot(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            cycle_id=cycle_id,
            slot_id=slot_id,
            actor_user_id=_get_actor_user_id(),
            payload={
                "label": request.form.get("label"),
                "description": request.form.get("description"),
                "menu_cycle_id": cycle_id,
            },
        )
        _flash_success("offshore.success.menu_cycle_slot_saved")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return _settings_redirect()


def _checkbox_enabled(value: object | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes")


def _parse_local_time(value: object | None):
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("offshore.validation.invalid_starts_at")
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        try:
            return datetime.strptime(raw, "%H:%M:%S").time()
        except ValueError as exc:
            raise ValueError("offshore.validation.invalid_starts_at") from exc


def _period_scope(result: dict[str, object]) -> tuple[int, str, str, dict[str, str]]:
    tenant_id = int(result.get("tenant_id") or 0)
    site_id = str(result.get("site_id") or "")
    locale = resolve_locale()
    labels = copy_for(locale)
    timezone_name = site_timezone_name(tenant_id, site_id)
    return tenant_id, site_id, timezone_name, labels


def _period_page_vm(result: dict[str, object]) -> dict[str, object]:
    tenant_id, site_id, timezone_name, labels = _period_scope(result)
    templates = _period_service.list_period_templates(tenant_id, site_id)
    periods = _period_service.list_work_periods(tenant_id, site_id)
    summary = period_dashboard_payload(tenant_id, site_id, locale=resolve_locale())
    serialized_templates = [
        serialize_template(template, resolve_locale(), _period_service.list_template_events(tenant_id, site_id, int(template.id)))
        for template in templates
    ]
    serialized_periods = [
        serialize_period(period, resolve_locale(), timezone_name, _period_service.list_service_events(tenant_id, site_id, int(period.id)))
        for period in periods
    ]
    return {
        "lang": resolve_locale(),
        "theme": resolve_theme(),
        "labels": labels,
        "tenant_id": tenant_id,
        "site_id": site_id,
        "tenant_name": result.get("tenant_name"),
        "site_name": result.get("site_name"),
        "user_name": current_app.config.get("_offshore_role") or request.headers.get("X-User-Role") or "Inloggad",
        "user_role": request.headers.get("X-User-Role") or None,
        "allow_site_switch": (request.headers.get("X-User-Role") or "").strip().lower() in ("admin", "superuser"),
        "page_title": labels["offshore.periods.title"],
        "page_subtitle": labels["offshore.periods.subtitle"],
        "template_options": serialized_templates,
        "period_options": serialized_periods,
        "work_positions": [
            {"id": row.id, "name": row.name, "code": row.code}
            for row in _period_service.list_work_positions(tenant_id, site_id)
        ],
        "menu_cycles": [
            {"id": row.id, "name": row.name, "is_active": bool(row.is_active)}
            for row in _period_service.list_menu_cycles(tenant_id, site_id)
        ],
        "menu_cycle_slots": [
            {"id": slot.id, "menu_cycle_id": slot.menu_cycle_id, "cycle_index": slot.cycle_index, "label": slot.label, "is_active": bool(slot.is_active)}
            for slot in _period_service.list_menu_cycle_slots(tenant_id, site_id)
        ],
        "period_status_options": [
            {"value": value, "label": labels.get(f"offshore.periods.status.{value}", value)}
            for value in WORK_PERIOD_STATUSES
        ],
        "event_status_options": [
            {"value": value, "label": labels.get(f"offshore.event.status.{value}", value)}
            for value in PERIOD_TEMPLATE_EVENT_STATUSES
        ],
        "summary": summary,
        "timezone_name": timezone_name,
        "current_period": summary.get("current_period"),
        "next_period": summary.get("next_period"),
        "upcoming_event_count": summary.get("upcoming_event_count"),
        "has_templates": summary.get("has_templates"),
        "overlap_warnings": summary.get("overlap_warnings"),
    }

def _template_page_vm(result: dict[str, object], *, template_id: int | None = None) -> dict[str, object]:
    tenant_id, site_id, timezone_name, labels = _period_scope(result)
    templates = _period_service.list_period_templates(tenant_id, site_id)
    current_template = _period_service.get_period_template(tenant_id, site_id, template_id) if template_id is not None else None
    template_events = _period_service.list_template_events(tenant_id, site_id, template_id) if template_id is not None else []
    serialized_templates = [
        serialize_template(template, resolve_locale(), _period_service.list_template_events(tenant_id, site_id, int(template.id)))
        for template in templates
    ]
    return {
        "lang": resolve_locale(),
        "theme": resolve_theme(),
        "labels": labels,
        "tenant_id": tenant_id,
        "site_id": site_id,
        "tenant_name": result.get("tenant_name"),
        "site_name": result.get("site_name"),
        "user_name": current_app.config.get("_offshore_role") or request.headers.get("X-User-Role") or "Inloggad",
        "user_role": request.headers.get("X-User-Role") or None,
        "allow_site_switch": (request.headers.get("X-User-Role") or "").strip().lower() in ("admin", "superuser"),
        "page_title": labels["offshore.period_templates.title"],
        "page_subtitle": labels["offshore.period_templates.subtitle"],
        "timezone_name": timezone_name,
        "template_options": serialized_templates,
        "selected_template": serialize_template(current_template, resolve_locale(), template_events) if current_template else None,
        "template_events": [serialize_template_event(event, resolve_locale(), current_template) for event in template_events],
        "work_positions": [
            {"id": row.id, "name": row.name, "code": row.code}
            for row in _period_service.list_work_positions(tenant_id, site_id)
        ],
        "has_templates": bool(templates),
        "event_status_options": [
            {"value": value, "label": labels.get(f"offshore.event.status.{value}", value)}
            for value in PERIOD_TEMPLATE_EVENT_STATUSES
        ],
    }


@bp.get("/period-templates")
@require_roles(*VIEWER_ROLES)
def period_templates():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    vm = _template_page_vm(result)
    return render_template("offshore2/period_templates.html", vm=vm)


@bp.post("/period-templates")
@require_roles(*MANAGER_ROLES)
def create_period_template():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        template = _period_service.create_period_template(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            name=request.form.get("name"),
            description=request.form.get("description"),
            duration_days=request.form.get("duration_days") or 1,
            start_weekday=request.form.get("start_weekday") or None,
            active=_checkbox_enabled(request.form.get("active", "1")),
            sort_order=request.form.get("sort_order") or None,
        )
        _flash_success("offshore.success.period_template_created")
        return redirect(url_for("offshore2.period_template_detail", template_id=template.id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.get("/period-templates/<int:template_id>")
@require_roles(*VIEWER_ROLES)
def period_template_detail(template_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    vm = _template_page_vm(result, template_id=template_id)
    if not vm.get("selected_template"):
        return not_found("offshore.validation.cross_site")
    return render_template("offshore2/period_templates.html", vm=vm)


@bp.post("/period-templates/<int:template_id>")
@require_roles(*MANAGER_ROLES)
def update_period_template(template_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        template = _period_service.update_period_template(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            template_id=template_id,
            name=request.form.get("name"),
            description=request.form.get("description"),
            duration_days=request.form.get("duration_days") or 1,
            start_weekday=request.form.get("start_weekday") or None,
            active=_checkbox_enabled(request.form.get("active", "1")),
            sort_order=request.form.get("sort_order") or None,
        )
        _flash_success("offshore.success.period_template_saved")
        return redirect(url_for("offshore2.period_template_detail", template_id=template.id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.post("/period-templates/<int:template_id>/archive")
@require_roles(*MANAGER_ROLES)
def archive_period_template(template_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _period_service.archive_period_template(tenant_id=result.get("tenant_id"), site_id=result.get("site_id"), template_id=template_id)
        _flash_success("offshore.success.period_template_archived")
        return redirect(url_for("offshore2.period_templates"))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.post("/period-templates/<int:template_id>/events")
@require_roles(*MANAGER_ROLES)
def create_period_template_event(template_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        event = _period_service.add_template_event(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            template_id=template_id,
            day_offset=request.form.get("day_offset") or 0,
            local_time=_parse_local_time(request.form.get("local_time")),
            service_code=request.form.get("service_code"),
            display_name=request.form.get("display_name"),
            work_position_id=request.form.get("work_position_id") or None,
            default_portions=request.form.get("default_portions") or None,
            notes=request.form.get("notes"),
            sort_order=request.form.get("sort_order") or None,
            active=_checkbox_enabled(request.form.get("active", "1")),
        )
        _flash_success("offshore.success.period_template_event_created")
        return redirect(url_for("offshore2.period_template_detail", template_id=template_id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.post("/period-templates/<int:template_id>/events/<int:event_id>")
@require_roles(*MANAGER_ROLES)
def update_period_template_event(template_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _period_service.update_template_event(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            template_id=template_id,
            event_id=event_id,
            payload={
                "day_offset": request.form.get("day_offset"),
                "local_time": request.form.get("local_time"),
                "service_code": request.form.get("service_code"),
                "display_name": request.form.get("display_name"),
                "work_position_id": request.form.get("work_position_id") or None,
                "default_portions": request.form.get("default_portions") or None,
                "notes": request.form.get("notes"),
                "sort_order": request.form.get("sort_order") or None,
                "active": _checkbox_enabled(request.form.get("active", "1")),
            },
        )
        _flash_success("offshore.success.period_template_event_saved")
        return redirect(url_for("offshore2.period_template_detail", template_id=template_id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.post("/period-templates/<int:template_id>/events/<int:event_id>/delete")
@require_roles(*MANAGER_ROLES)
def delete_period_template_event(template_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _period_service.delete_template_event(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            template_id=template_id,
            event_id=event_id,
        )
        _flash_success("offshore.success.period_template_event_deleted")
        return redirect(url_for("offshore2.period_template_detail", template_id=template_id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.get("/periods")
@require_roles(*VIEWER_ROLES)
def periods():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    vm = _period_page_vm(result)
    return render_template("offshore2/periods.html", vm=vm)


@bp.post("/periods")
@require_roles("editor", "admin", "superuser")
def create_period():
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        template_id = request.form.get("period_template_id")
        if template_id:
            generation = _period_service.create_work_period_from_template(
                tenant_id=result.get("tenant_id"),
                site_id=result.get("site_id"),
                period_template_id=int(template_id),
                starts_at=datetime.fromisoformat(f"{request.form.get('start_date')}T{request.form.get('start_time')}"),
                name=request.form.get("name"),
                menu_cycle_id=request.form.get("menu_cycle_id") or None,
                start_menu_cycle_slot_id=request.form.get("start_menu_cycle_slot_id") or None,
                notes=request.form.get("notes"),
            )
            _flash_success("offshore.success.work_period_created")
            return redirect(url_for("offshore2.period_detail", period_id=generation.work_period.id))
        period = _period_service.create_work_period(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            name=request.form.get("name"),
            starts_at=datetime.fromisoformat(f"{request.form.get('start_date')}T{request.form.get('start_time')}"),
            ends_at=datetime.fromisoformat(f"{request.form.get('end_date')}T{request.form.get('end_time')}"),
            menu_cycle_id=request.form.get("menu_cycle_id") or None,
            start_menu_cycle_slot_id=request.form.get("start_menu_cycle_slot_id") or None,
            status=request.form.get("status") or "planned",
            notes=request.form.get("notes"),
        )
        _flash_success("offshore.success.work_period_created")
        return redirect(url_for("offshore2.period_detail", period_id=period.id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.get("/periods/<int:period_id>")
@require_roles(*VIEWER_ROLES)
def period_detail(period_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    tenant_id, site_id, timezone_name, labels = _period_scope(result)
    period = _period_service.get_work_period(tenant_id, site_id, period_id)
    if period is None:
        return not_found("offshore.validation.cross_site")
    events = _period_service.list_service_events(tenant_id, site_id, period_id)
    contexts = _menu_context_service.list_contexts_for_period(tenant_id=tenant_id, site_id=site_id, work_period_id=period_id)
    vm = _period_page_vm(result)
    vm.update({
        "selected_period": serialize_period(period, resolve_locale(), timezone_name, events),
        "period_events": [serialize_service_event(event, resolve_locale(), timezone_name) for event in events],
        "period_event_context_by_event_id": {
            context.service_event_id: {
                "service_date": context.service_date.isoformat(),
                "menu_cycle_id": context.menu_cycle_id,
                "start_menu_cycle_slot_id": context.start_menu_cycle_slot_id,
                "menu_cycle_slot_id": context.menu_cycle_slot_id,
                "menu_cycle_index": context.menu_cycle_index,
                "service_key": context.service_key,
                "resolution_status": context.resolution_status,
                "assignment_source": context.assignment_source,
                "match_status": context.match_status,
                "resolution_reason": context.resolution_reason,
                "manual_note": context.manual_note,
                "builder_publication_pin_id": context.builder_publication_pin_id,
                "builder_publication_year": context.builder_publication_year,
                "builder_publication_week": context.builder_publication_week,
                "builder_menu_id": context.builder_menu_id,
                "builder_menu_version": context.builder_menu_version,
            }
            for context in contexts
        },
        "period_event_contexts": [
            {
                "service_event_id": context.service_event_id,
                "service_date": context.service_date.isoformat(),
                "menu_cycle_id": context.menu_cycle_id,
                "start_menu_cycle_slot_id": context.start_menu_cycle_slot_id,
                "menu_cycle_slot_id": context.menu_cycle_slot_id,
                "menu_cycle_index": context.menu_cycle_index,
                "service_key": context.service_key,
                "resolution_status": context.resolution_status,
                "assignment_source": context.assignment_source,
                "match_status": context.match_status,
                "resolution_reason": context.resolution_reason,
                "manual_note": context.manual_note,
                "builder_publication_pin_id": context.builder_publication_pin_id,
                "builder_publication_year": context.builder_publication_year,
                "builder_publication_week": context.builder_publication_week,
                "builder_menu_id": context.builder_menu_id,
                "builder_menu_version": context.builder_menu_version,
            }
            for context in contexts
        ],
        "overlap_warnings": _period_service.detect_period_overlaps(tenant_id, site_id),
    })
    return render_template("offshore2/periods.html", vm=vm)


@bp.post("/periods/<int:period_id>")
@require_roles("editor", "admin", "superuser")
def update_period(period_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        period = _period_service.update_work_period(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            period_id=period_id,
            payload={
                "name": request.form.get("name"),
                "status": request.form.get("status"),
                "notes": request.form.get("notes"),
                "starts_at": datetime.fromisoformat(f"{request.form.get('start_date')}T{request.form.get('start_time')}") if request.form.get("start_date") and request.form.get("start_time") else None,
                "ends_at": datetime.fromisoformat(f"{request.form.get('end_date')}T{request.form.get('end_time')}") if request.form.get("end_date") and request.form.get("end_time") else None,
                "period_template_id": request.form.get("period_template_id") or None,
                "menu_cycle_id": request.form.get("menu_cycle_id") or None,
                "start_menu_cycle_slot_id": request.form.get("start_menu_cycle_slot_id") or None,
            },
        )
        _flash_success("offshore.success.work_period_saved")
        return redirect(url_for("offshore2.period_detail", period_id=period.id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.post("/periods/<int:period_id>/service-events/<int:event_id>")
@require_roles("editor", "admin", "superuser")
def update_period_service_event(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        _period_service.update_service_event(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            event_id=event_id,
            payload={
                "status": request.form.get("status"),
                "display_name": request.form.get("display_name"),
                "service_code": request.form.get("service_code"),
                "expected_portions": request.form.get("expected_portions"),
                "work_position_id": request.form.get("work_position_id") or None,
                "notes": request.form.get("notes"),
                "starts_at": datetime.fromisoformat(f"{request.form.get('start_date')}T{request.form.get('start_time')}") if request.form.get("start_date") and request.form.get("start_time") else None,
            },
        )
        _flash_success("offshore.success.service_event_saved")
        return redirect(url_for("offshore2.period_detail", period_id=period_id))
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)


@bp.get("/periods/<int:period_id>/service-events/<int:event_id>/menu-context")
@require_roles(*VIEWER_ROLES)
def period_service_event_menu_context(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        context = _menu_context_service.resolve_context(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            service_event_id=event_id,
        )
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)

    return jsonify(
        {
            "ok": True,
            "context": {
                "service_date": context.service_date.isoformat(),
                "menu_cycle_id": context.menu_cycle_id,
                "start_menu_cycle_slot_id": context.start_menu_cycle_slot_id,
                "menu_cycle_slot_id": context.menu_cycle_slot_id,
                "menu_cycle_index": context.menu_cycle_index,
                "service_key": context.service_key,
                "resolution_status": context.resolution_status,
                "assignment_source": context.assignment_source,
                "match_status": context.match_status,
                "resolution_reason": context.resolution_reason,
                "manual_note": context.manual_note,
                "builder_publication_pin_id": context.builder_publication_pin_id,
                "builder_publication_year": context.builder_publication_year,
                "builder_publication_week": context.builder_publication_week,
                "builder_menu_id": context.builder_menu_id,
                "builder_menu_version": context.builder_menu_version,
            },
        }
    )


@bp.get("/periods/<int:period_id>/service-events/<int:event_id>/calendar-readiness")
@require_roles(*VIEWER_ROLES)
def period_service_event_calendar_readiness(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        period = _period_service.get_work_period(result.get("tenant_id"), result.get("site_id"), period_id)
        event = _period_service.list_service_events(result.get("tenant_id"), result.get("site_id"), period_id)
        selected_event = next((row for row in event if int(row.id) == int(event_id)), None)
        context = _menu_context_service.resolve_context(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            service_event_id=event_id,
        )
        if period is None or selected_event is None:
            return not_found("offshore.validation.cross_site")
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)

    editable = (request.headers.get("X-User-Role") or "").strip().lower() in ("admin", "superuser", "editor") and getattr(period, "status", "") != "completed"
    category = "service"
    return jsonify(
        {
            "source_module": "modules.offshore2",
            "source_type": "service_event",
            "source_id": str(event_id),
            "tenant_id": result.get("tenant_id"),
            "site_id": result.get("site_id"),
            "starts_at": selected_event.starts_at.isoformat(),
            "title": selected_event.display_name,
            "category": category,
            "status": selected_event.status,
            "menu_context_status": context.resolution_status,
            "detail_url": url_for("offshore2.period_detail", period_id=period_id),
            "editable": editable,
        }
    )


@bp.post("/periods/<int:period_id>/service-events/<int:event_id>/menu-context/refresh")
@require_roles("editor", "admin", "superuser")
def refresh_period_service_event_menu_context(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        context = _menu_context_service.sync_service_event_context(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            service_event_id=event_id,
            source="automatic",
        )
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return jsonify({"ok": True, "context": {"resolution_status": context.resolution_status, "assignment_source": context.assignment_source}})


@bp.post("/periods/<int:period_id>/service-events/<int:event_id>/menu-context/manual")
@require_roles("editor", "admin", "superuser")
def manual_period_service_event_menu_context(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        context = _menu_context_service.sync_service_event_context(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            service_event_id=event_id,
            source="manual",
            manual_note=request.form.get("manual_note"),
            force=True,
        )
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return jsonify({"ok": True, "context": {"resolution_status": context.resolution_status, "assignment_source": context.assignment_source}})


@bp.post("/periods/<int:period_id>/service-events/<int:event_id>/menu-context/clear")
@require_roles("editor", "admin", "superuser")
def clear_period_service_event_menu_context(period_id: int, event_id: int):
    result = _context_or_redirect()
    if not isinstance(result, dict):
        return result
    try:
        context = _menu_context_service.clear_manual_assignment(
            tenant_id=result.get("tenant_id"),
            site_id=result.get("site_id"),
            work_period_id=period_id,
            service_event_id=event_id,
        )
    except LookupError:
        return not_found("offshore.validation.cross_site")
    except ValueError as exc:
        return _handle_validation_error(exc)
    return jsonify({"ok": True, "context": {"resolution_status": context.resolution_status, "assignment_source": context.assignment_source}})
