from __future__ import annotations

import os
from flask import Blueprint, render_template, request, current_app, Response

bp = Blueprint("admin_demo_ui", __name__, url_prefix="/demo")


@bp.after_request
def _demo_csp(resp):  # type: ignore[override]
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


@bp.get("/")
def demo_index():
    """Minimal admin demo UI.

    Shows simple-auth login, departments listing with ETag/If-None-Match demo,
    and Alt2 week toggle flow. Uses fetch() against /admin endpoints and
    includes X-CSRF-Token from cookie for writes.
    """
    # Surface an explicit flag so the page can show a banner in staging
    staging_demo = os.getenv("STAGING_SIMPLE_AUTH", "0").lower() in ("1", "true", "yes")
    try:
        return render_template("demo_admin.html", staging_demo=staging_demo)
    except Exception:
        # Defensive fallback to avoid 500s in staging if template/rendering fails for any reason.
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


@bp.head("/")
def demo_head_index():
    """HEAD handler to ensure HEAD /demo/ returns headers without 500.

    Flask normally maps HEAD to GET automatically, but some proxy/client
    combinations can surface edge-cases. Return an empty 200; after_request
    will still attach CSP and Cache-Control headers.
    """
    return "", 200


@bp.get("/ping")
def demo_ping() -> dict[str, str]:
    """Lightweight ping for demo readiness checks."""
    return {"ok": "true"}
