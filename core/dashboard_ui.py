from __future__ import annotations

from flask import Blueprint, current_app, g, redirect, render_template, url_for
from werkzeug.wrappers.response import Response as WsgiResponse

from .app_sessions import get_session
from .roles import to_canonical

# Keep template folder relative to core package so we can reuse core/templates/ui
bp = Blueprint("dashboard", __name__, template_folder="templates", static_folder="static")

@bp.get("/")
def root_redirect() -> WsgiResponse:
    """Landing: if logged in, redirect to dashboard; else render a minimal landing (200)."""
    sess = get_session()
    if sess:
        return redirect(url_for("dashboard.dashboard_home"), code=302)
    # Keep minimal landing for now
    return render_template("ui/dashboard_landing.html")


@bp.get("/dashboard")
def dashboard_home():  # pragma: no cover simple render
    # AuthN: redirect to landing when not logged in (HTML UX)
    sess = get_session()
    if not sess:
        return redirect(url_for("dashboard.root_redirect"), code=302)
    # RBAC: allow canonical roles {admin, editor}
    if to_canonical(sess["role"]) not in ("admin", "editor"):
        return ("Forbidden", 403)
    # Feature flag gate: ff.dashboard.enabled must be enabled
    name = "ff.dashboard.enabled"
    reg = getattr(current_app, "feature_registry", None)
    tenant_overrides = getattr(g, "tenant_feature_flags", {}) or {}
    enabled = tenant_overrides.get(name)
    if enabled is None:
        enabled = bool(reg and reg.enabled(name))
    if not enabled:
        # Standard 404 for disabled feature
        return ("Not Found", 404)
    resp = current_app.make_response(render_template("ui/dashboard.html"))
    resp.headers["Cache-Control"] = "no-store"
    return resp
