from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from core.auth import require_roles
from core.http_errors import forbidden, not_found

from .i18n import normalize_locale
from .permissions import FEATURE_FLAG, VIEWER_ROLES, MANAGER_ROLES, gate_or_404
from .services import build_dashboard_vm, build_settings_vm, resolve_active_context, resolve_locale, resolve_theme

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
    locale = resolve_locale()
    theme = resolve_theme()
    vm = build_settings_vm(
        locale=locale,
        theme=theme,
        role=request.headers.get("X-User-Role") or None,
        tenant_id=result.get("tenant_id"),
        site_id=result.get("site_id"),
        tenant_name=result.get("tenant_name"),
        site_name=result.get("site_name"),
    )
    return render_template("offshore2/settings.html", vm=vm)
