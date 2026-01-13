from __future__ import annotations

from flask import Blueprint, render_template, session, redirect, g, current_app
from .http_errors import forbidden, not_found

bp = Blueprint("dashboard_ui", __name__)


def _dashboard_enabled() -> bool:
    try:
        override = getattr(g, "tenant_feature_flags", {}).get("ff.dashboard.enabled")
        if override is not None:
            return bool(override)
        reg = getattr(current_app, "feature_registry", None)
        return bool(reg.enabled("ff.dashboard.enabled")) if reg else False
    except Exception:
        return False


@bp.get("/dashboard")
def dashboard():
    # Unauthenticated -> redirect to root
    role = session.get("role")
    if not role:
        return redirect("/")
    # Feature flag gate
    if not _dashboard_enabled():
        return not_found("dashboard_disabled")
    # RBAC: only admin/editor allowed
    if role not in ("admin", "editor"):
        return forbidden("Insufficient permissions")
    # Basic template render (IDs used by tests)
    return render_template("ui/dashboard.html")
