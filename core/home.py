from __future__ import annotations

from flask import Blueprint, render_template, redirect, session, g, current_app

bp = Blueprint("home", __name__, template_folder="templates", static_folder="static")


@bp.get("/home")
def index():  # pragma: no cover - legacy landing retained under /home
    try:
        # Preserve original behavior under /home for manual access
        role = session.get("role")
        tid = session.get("tenant_id")
        if role and tid is not None:
            try:
                ff = getattr(g, "tenant_feature_flags", {})
                enabled = ff.get("ff.dashboard.enabled")
                if enabled is None:
                    reg = getattr(current_app, "feature_registry", None)
                    enabled = reg.enabled("ff.dashboard.enabled") if reg else False
                if enabled:
                    return redirect("/dashboard")
            except Exception:
                pass
        return render_template("home.html")
    except Exception:
        return redirect("/docs/")
