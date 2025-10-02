from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_roles

from .api_types import (
    ErrorResponse,
    FeatureToggleResponse,
    TenantCreateResponse,
    TenantListResponse,
)
from .db import get_session
from .feature_service import FeatureService
from .models import Tenant, TenantFeatureFlag, TenantMetadata

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/tenants")
@require_roles("superuser")
def list_tenants() -> TenantListResponse | ErrorResponse:  # pragma: no cover simple pass-through
    db = get_session()
    try:
        rows = db.query(Tenant).all()
        raw_list: list[dict[str, object]] = []
        for t in rows:
            feats = db.query(TenantFeatureFlag).filter_by(tenant_id=t.id, enabled=True).all()
            meta = db.query(TenantMetadata).filter_by(tenant_id=t.id).first()
            raw_list.append({
                "id": t.id,
                "name": t.name,
                "active": t.active,
                "kind": meta.kind if meta else None,
                "description": meta.description if meta else None,
                "features": [f.name for f in feats],
            })
        return cast(TenantListResponse, {"ok": True, "tenants": raw_list})
    finally:
        db.close()

@bp.post("/tenants")
@require_roles("superuser")
def create_tenant() -> TenantCreateResponse | ErrorResponse:
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    modules = data.get("modules") or []
    admin_email = data.get("admin_email")
    admin_password = data.get("admin_password")
    kind = data.get("kind")
    description = data.get("description")
    if not (name and modules and admin_email and admin_password):
        return jsonify({"ok": False, "error": "missing fields"}), 400  # type: ignore[return-value]
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    tenant_id = svc.create_tenant_with_admin(name, modules, admin_email, admin_password)
    if kind or description:
        msvc = current_app.tenant_metadata_service  # type: ignore[attr-defined]
        msvc.upsert(tenant_id, kind, description)
    return cast(TenantCreateResponse, {"ok": True, "tenant_id": tenant_id})

@bp.post("/features/toggle")
@require_roles("superuser","admin")
def toggle_feature() -> FeatureToggleResponse | ErrorResponse:
    from flask import session
    data = request.get_json(silent=True) or {}
    feature = data.get("feature")
    enabled = data.get("enabled")
    target_tenant_id = data.get("tenant_id") if session.get("role") == "superuser" else session.get("tenant_id")
    if not feature or enabled is None:
        return jsonify({"ok": False, "error": "missing feature or enabled"}), 400  # type: ignore[return-value]
    if not target_tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    if enabled:
        svc.enable(target_tenant_id, feature)
    else:
        svc.disable(target_tenant_id, feature)
    return {"ok": True, "tenant_id": target_tenant_id, "feature": feature, "enabled": bool(enabled)}

@bp.post("/feature_flags")
@require_roles("superuser","admin")
def tenant_feature_flag_toggle() -> FeatureToggleResponse | ErrorResponse:
    from flask import session
    data = request.get_json(silent=True) or {}
    raw_name = data.get("name")
    enabled = data.get("enabled")
    if raw_name is None or enabled is None:
        return jsonify({"error":"validation_error","message":"name and enabled required","ok": False}), 400  # type: ignore[return-value]
    name = str(raw_name).strip()
    if not name:
        return jsonify({"error":"validation_error","message":"name empty","ok": False}), 400  # type: ignore[return-value]
    role = session.get("role")
    target_tenant_id = data.get("tenant_id") if role == "superuser" else session.get("tenant_id")
    if not target_tenant_id:
        return jsonify({"error":"validation_error","message":"tenant context missing","ok": False}), 400  # type: ignore[return-value]
    try:
        tid = int(target_tenant_id)
    except Exception:
        return jsonify({"error":"validation_error","message":"invalid tenant_id","ok": False}), 400  # type: ignore[return-value]
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    if bool(enabled):
        svc.enable(tid, name)
    else:
        svc.disable(tid, name)
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return cast(FeatureToggleResponse, {"ok": True, "tenant_id": tid, "feature": name, "enabled": bool(enabled), "features": [f.name for f in feats]})
    finally:
        db.close()

@bp.get("/feature_flags")
@require_roles("superuser","admin")
def tenant_feature_flags_list() -> FeatureToggleResponse | ErrorResponse:
    from flask import session
    role = session.get("role")
    if role == "superuser":
        q_tid = request.args.get("tenant_id") or session.get("tenant_id")
    else:
        q_tid = session.get("tenant_id")
    if not q_tid:
        return jsonify({"error":"validation_error","message":"tenant context missing","ok": False}), 400  # type: ignore[return-value]
    try:
        tid = int(q_tid)
    except Exception:
        return jsonify({"error":"validation_error","message":"invalid tenant_id","ok": False}), 400  # type: ignore[return-value]
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return cast(FeatureToggleResponse, {"ok": True, "tenant_id": tid, "features": [f.name for f in feats]})
    finally:
        db.close()


# --- Legacy cook flag usage listing ---
@bp.get("/flags/legacy-cook")
@require_roles("admin")
def list_legacy_cook_tenants() -> TenantListResponse | ErrorResponse:  # pragma: no cover (covered via dedicated tests)
    """Return tenants where 'allow_legacy_cook_create' flag is enabled.

    Implementation notes:
    * We filter directly on TenantFeatureFlag for efficiency.
    * Returns standard TenantListResponse shape (subset of fields + features list).
    * Only admin/superuser (via require_roles) may access.
    """
    FLAG_NAME = "allow_legacy_cook_create"
    db = get_session()
    try:
        # Query tenants having the flag enabled
        rows = (
            db.query(Tenant)
            .join(TenantFeatureFlag, TenantFeatureFlag.tenant_id == Tenant.id)
            .filter(TenantFeatureFlag.name == FLAG_NAME, TenantFeatureFlag.enabled.is_(True))
            .all()
        )
        out: list[dict[str, object]] = []
        for t in rows:
            feats_enabled = (
                db.query(TenantFeatureFlag.name)
                .filter_by(tenant_id=t.id, enabled=True)
                .all()
            )
            out.append({
                "id": t.id,
                "name": t.name,
                "active": t.active,
                "features": [f[0] for f in feats_enabled],
            })
        return cast(TenantListResponse, {"ok": True, "tenants": out})
    finally:
        db.close()
