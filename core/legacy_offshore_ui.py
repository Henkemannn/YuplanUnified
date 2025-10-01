"""Legacy Offshore UI adapter blueprint.

First step: expose /superuser/panel using unified Tenants as 'rigs'.
We DO NOT import the entire legacy app; we only reuse its template.
Later we can progressively map more routes.
"""
from __future__ import annotations

from flask import Blueprint, render_template, session

from .auth import require_roles
from .db import get_session
from .models import Tenant, TenantMetadata

bp = Blueprint(
    "legacy_offshore_ui",
    __name__,
    template_folder="../legacy/offshore/templates",  # relative to this file
    static_folder="../legacy/offshore/static"
)

def _tenant_to_rig_row(t: Tenant, meta: TenantMetadata | None):
    return {
        "id": t.id,
        "name": t.name,
        "description": (meta.description if meta and meta.description else ""),
        "kind": (meta.kind if meta and meta.kind else None),
    }

@bp.before_app_request
def _inject_superuser_flag():  # minimal compatibility; unify concept
    if session.get("role") == "superuser" and "superuser" not in session:
        session["superuser"] = True  # legacy templates check this sometimes


@bp.route("/superuser/panel", methods=["GET"])
@require_roles("superuser")
def superuser_panel_adapter():
    # Pull all tenants and present as rigs
    db = get_session()
    try:
        tenants = db.query(Tenant).order_by(Tenant.id).all()
        metas = {m.tenant_id: m for m in db.query(TenantMetadata).all()}
    finally:
        db.close()
    rigs = [_tenant_to_rig_row(t, metas.get(t.id)) for t in tenants]
    # Maintain template contract expected by superuser_panel.html
    return render_template(
        "superuser_panel.html",
        admins=[],  # later: unify admins list (users with role=admin)
        rigs=rigs,
        error=None,
        current_rig_id=None,
        current_rig_name=None,
        DEMO_MODE=False,
    )
