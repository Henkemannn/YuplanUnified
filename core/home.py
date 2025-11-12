from __future__ import annotations

from flask import Blueprint, render_template, redirect, session, g, current_app

bp = Blueprint("home", __name__, template_folder="templates", static_folder="static")


@bp.get("/")
def index():  # pragma: no cover - tiny landing
    try:
        # If user is logged in and dashboard feature flag is on -> redirect to /dashboard
        role = session.get("role")
        tid = session.get("tenant_id")
        if role and tid is not None:
            # Check feature flag ff.dashboard.enabled
            try:
                # Prefer tenant override via g.tenant_feature_flags if present
                ff = getattr(g, "tenant_feature_flags", {})
                enabled = ff.get("ff.dashboard.enabled")
                if enabled is None:
                    reg = getattr(current_app, "feature_registry", None)
                    enabled = reg.enabled("ff.dashboard.enabled") if reg else False
                if enabled:
                    return redirect("/dashboard")
            except Exception:
                pass
        # Otherwise render simple landing page
        return render_template("home.html")
    except Exception:
        # In case templates not available for some reason, soft-fallback to /docs
        return redirect("/docs/")
