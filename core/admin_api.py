from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_roles

from .db import get_session
from .feature_service import FeatureService
from .models import Tenant, TenantFeatureFlag, TenantMetadata

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/tenants")
@require_roles("superuser")
def list_tenants():
    db = get_session()
    try:
        rows = db.query(Tenant).all()
        out = []
        for t in rows:
            feats = db.query(TenantFeatureFlag).filter_by(tenant_id=t.id, enabled=True).all()
            meta = db.query(TenantMetadata).filter_by(tenant_id=t.id).first()
            out.append({
                "id": t.id,
                "name": t.name,
                "active": t.active,
                "kind": meta.kind if meta else None,
                "description": meta.description if meta else None,
                "features": [f.name for f in feats]
            })
        return {"ok": True, "tenants": out}
    finally:
        db.close()

@bp.post("/tenants")
@require_roles("superuser")
def create_tenant():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    modules = data.get("modules") or []
    admin_email = data.get("admin_email")
    admin_password = data.get("admin_password")
    kind = data.get("kind")
    description = data.get("description")
    if not (name and modules and admin_email and admin_password):
        return jsonify({"ok": False, "error": "missing fields"}), 400
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    tenant_id = svc.create_tenant_with_admin(name, modules, admin_email, admin_password)
    # optional metadata
    if kind or description:
        msvc = current_app.tenant_metadata_service  # type: ignore[attr-defined]
        msvc.upsert(tenant_id, kind, description)
    return {"ok": True, "tenant_id": tenant_id}


@bp.post("/features/toggle")
@require_roles("superuser","admin")
def toggle_feature():
    """Enable or disable a feature flag for the current tenant (admin) or specified tenant (superuser).

    Payload JSON:
      {"feature": "menus", "enabled": true, "tenant_id": optional-int}
    - superuser may pass tenant_id to change any tenant.
    - admin will always act on their own session tenant.
    """
    from flask import session
    data = request.get_json(silent=True) or {}
    feature = data.get("feature")
    enabled = data.get("enabled")
    target_tenant_id = data.get("tenant_id") if session.get("role") == "superuser" else session.get("tenant_id")
    if not feature or enabled is None:
        return jsonify({"ok": False, "error": "missing feature or enabled"}), 400
    if not target_tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    if enabled:
        svc.enable(target_tenant_id, feature)
    else:
        svc.disable(target_tenant_id, feature)
    return {"ok": True, "tenant_id": target_tenant_id, "feature": feature, "enabled": bool(enabled)}


@bp.post("/feature_flags")
@require_roles("superuser","admin")
def tenant_feature_flag_toggle():
    """Tenant-scoped feature flag toggle (idempotent).

    Request JSON:
      {
        "name": "inline_ui",
        "enabled": true,
        "tenant_id": 5   # optional, only honored for superuser
      }

    Rules:
      - superuser may target any tenant via tenant_id.
      - admin may only affect their own tenant (ignored tenant_id).
      - name required, enabled required (bool coercible).
    """
    from flask import session
    data = request.get_json(silent=True) or {}
    raw_name = data.get("name")
    enabled = data.get("enabled")
    if raw_name is None or enabled is None:
        return jsonify({"error":"validation_error","message":"name and enabled required"}), 400
    name = str(raw_name).strip()
    if not name:
        return jsonify({"error":"validation_error","message":"name empty"}), 400
    role = session.get("role")
    target_tenant_id = data.get("tenant_id") if role == "superuser" else session.get("tenant_id")
    if not target_tenant_id:
        return jsonify({"error":"validation_error","message":"tenant context missing"}), 400
    try:
        tid = int(target_tenant_id)
    except Exception:
        return jsonify({"error":"validation_error","message":"invalid tenant_id"}), 400
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    if bool(enabled):
        svc.enable(tid, name)
    else:
        svc.disable(tid, name)
    # Return current enabled set for convenience
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return {"ok": True, "tenant_id": tid, "feature": name, "enabled": bool(enabled), "features": [f.name for f in feats]}
    finally:
        db.close()


@bp.get("/feature_flags")
@require_roles("superuser","admin")
def tenant_feature_flags_list():
    """List enabled feature flags for a tenant.

    Query params:
      tenant_id (optional, superuser only) – if omitted superuser must supply or we default to current session tenant if present.
    Admin: always bound to their own tenant; tenant_id query parameter ignored.
    Response: {ok, tenant_id, features:[...]}.
    """
    from flask import session
    role = session.get("role")
    if role == "superuser":
        q_tid = request.args.get("tenant_id") or session.get("tenant_id")
    else:
        q_tid = session.get("tenant_id")
    if not q_tid:
        return jsonify({"error":"validation_error","message":"tenant context missing"}), 400
    try:
        tid = int(q_tid)
    except Exception:
        return jsonify({"error":"validation_error","message":"invalid tenant_id"}), 400
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return {"ok": True, "tenant_id": tid, "features": [f.name for f in feats]}
    finally:
        db.close()
