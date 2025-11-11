from __future__ import annotations

import os
from flask import Blueprint, render_template, request

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
    return render_template("demo_admin.html", staging_demo=staging_demo)
