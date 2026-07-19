from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from core.auth import require_roles
from core.http_errors import forbidden, not_found

from .i18n import normalize_locale
from .permissions import FEATURE_FLAG, VIEWER_ROLES, MANAGER_ROLES, gate_or_404
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
