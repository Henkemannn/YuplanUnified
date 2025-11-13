from __future__ import annotations

import os
from flask import Blueprint, render_template, request, current_app, Response

bp = Blueprint("admin_demo_ui", __name__, url_prefix="/demo")


@bp.after_request
def _demo_csp(resp):
    """Attach a conservative CSP for demo responses only."""
    try:
        # Only set for responses under this blueprint
        if request.blueprint == bp.name:
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self'"
            )
            # Ensure demo pages are never cached to avoid stale ETags/state during demos
            resp.headers["Cache-Control"] = "no-store"
    except Exception:
        pass
    return resp


def _render_demo_index():
    """Render the demo index page with safe fallback on errors."""
    staging_demo = os.getenv("STAGING_SIMPLE_AUTH", "0").lower() in ("1", "true", "yes")
    demo_ui_enabled = os.getenv("DEMO_UI", "0").lower() in ("1", "true", "yes")
    # Gate CSV import preview: enabled on staging by default, otherwise via env CSV_IMPORT_PREVIEW=1
    csv_import_preview_enabled = staging_demo or (
        os.getenv("CSV_IMPORT_PREVIEW", "0").lower() in ("1", "true", "yes")
    )
    # Cache-busting token for static assets (read VERSION if present)
    asset_version = "dev"
    try:
        from flask import current_app as _ca
        ver_path = os.path.join(_ca.root_path, "VERSION")
        if os.path.exists(ver_path):
            with open(ver_path, "r", encoding="utf-8") as f:
                asset_version = f.read().strip() or asset_version
    except Exception:
        pass
    try:
        return render_template(
            "demo_admin.html",
            staging_demo=staging_demo,
            demo_ui_enabled=demo_ui_enabled,
            csv_import_preview_enabled=csv_import_preview_enabled,
            asset_version=asset_version,
        )
    except Exception:
        try:
            current_app.logger.exception("/demo render failed; serving minimal fallback")
        except Exception:
            pass
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Demo</title></head>"
            "<body><h1>Demo UI</h1><p>Fallback view. /demo/ping is OK but template rendering failed."
            " Check static assets and template loading. </p></body></html>"
        )
        return Response(html, mimetype="text/html")


@bp.route("/", methods=["GET", "HEAD"], strict_slashes=False)
def demo_index():
    """Serve demo index for both /demo and /demo/ without redirects.

    HEAD returns empty 200 with headers; GET renders template with fallback.
    """
    if request.method == "HEAD":
        return "", 200
    return _render_demo_index()


@bp.route("", methods=["GET", "HEAD"], strict_slashes=False)
def demo_index_noslash():
    """Serve demo index at /demo (no trailing slash) to avoid redirect."""
    if request.method == "HEAD":
        return "", 200
    return _render_demo_index()


@bp.get("/ping")
def demo_ping() -> dict[str, str]:
    """Lightweight ping for demo readiness checks."""
    return {"ok": "true"}
