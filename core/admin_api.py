from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_roles

from .api_types import (
    ErrorResponse,
    FeatureToggleResponse,
    LimitView,
    TenantCreateResponse,
    TenantListResponse,
)
from .db import get_session
from .feature_service import FeatureService
from .models import Tenant, TenantFeatureFlag, TenantMetadata
from .pagination import parse_page_params, make_page_response
from .limit_registry import list_default_names, list_tenant_names, get_limit
from .limit_registry import set_override, delete_override
from . import metrics as metrics_mod
from typing import cast as _cast, Literal

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


@bp.get("/limits")
@require_roles("admin")
def list_effective_limits():  # type: ignore[return-value]
    """List effective rate limits.

    Query params:
      tenant_id: if provided, include tenant overrides; else list only defaults.
      name: filter to a single limit name; if not found and tenant provided, return fallback only when name explicitly requested.
      page,size: standard pagination.
    """
    args = request.args
    page_req = parse_page_params(dict(args))
    tenant_q = args.get("tenant_id")
    name_filter = args.get("name")
    tenant_id: int | None = None
    if tenant_q:
        try:
            tenant_id = int(tenant_q)
        except Exception:
            return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    items: list[LimitView] = []
    names: list[str]
    if tenant_id is None:
        # defaults only
        names = list_default_names()
        if name_filter:
            names = [n for n in names if n == name_filter]
        for n in names:
            ld, src = get_limit(0, n)
            if src == "fallback":  # shouldn't happen without filter, skip noise
                continue
            assert src in ("tenant","default","fallback")
            items.append({"name": n, "quota": ld["quota"], "per_seconds": ld["per_seconds"], "source": src})
    else:
        # union defaults + tenant overrides
        union_names = set(list_default_names()) | set(list_tenant_names(tenant_id))
        if name_filter:
            if name_filter in union_names:
                union_names = {name_filter}
            else:
                # explicit name not present → allow fallback single row
                ld, src = get_limit(tenant_id, name_filter)
                if src == "fallback":
                    assert src in ("tenant","default","fallback")
                    items.append({"name": name_filter, "quota": ld["quota"], "per_seconds": ld["per_seconds"], "source": src, "tenant_id": tenant_id})
                return jsonify(make_page_response(items, page_req, len(items)))
        for n in sorted(union_names):
            ld, src = get_limit(tenant_id, n)
            if src == "fallback":
                continue  # hide fallback noise in union listing
            assert src in ("tenant","default","fallback")
            row: LimitView = {"name": n, "quota": ld["quota"], "per_seconds": ld["per_seconds"], "source": src, "tenant_id": tenant_id}
            items.append(row)
    total = len(items)
    start = (page_req["page"] - 1) * page_req["size"]
    page_slice = items[start:start + page_req["size"]]
    return jsonify(make_page_response(page_slice, page_req, total))


@bp.post("/limits")
@require_roles("admin")
def upsert_limit():  # type: ignore[return-value]
    from flask import session
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or session.get("tenant_id")
    name = data.get("name")
    quota = data.get("quota")
    per_seconds = data.get("per_seconds") or data.get("per")
    if tenant_id is None or name is None or quota is None or per_seconds is None:
        return jsonify({"ok": False, "error": "bad_request", "message": "tenant_id,name,quota,per_seconds required"}), 400
    try:
        tid = int(tenant_id)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    try:
        q = int(quota); p = int(per_seconds)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid quota/per_seconds"}), 400
    # clamp via registry helper
    ld_before, src_before = get_limit(tid, str(name))
    new_ld = set_override(tid, str(name), q, p)
    ld_after, src_after = get_limit(tid, str(name))
    updated = not (ld_before == ld_after and src_before == src_after)
    metrics_mod.increment("admin.limits.upsert", {
        "tenant_id": str(tid),
        "name": str(name),
        "updated": "true" if updated else "false",
        "actor_role": str(session.get("role")) if "session" in globals() else "unknown",
    })
    return jsonify({"ok": True, "item": {"tenant_id": tid, "name": str(name), "quota": ld_after["quota"], "per_seconds": ld_after["per_seconds"], "source": src_after}, "updated": updated})


@bp.delete("/limits")
@require_roles("admin")
def delete_limit():  # type: ignore[return-value]
    from flask import session
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or session.get("tenant_id")
    name = data.get("name")
    if tenant_id is None or name is None:
        return jsonify({"ok": False, "error": "bad_request", "message": "tenant_id,name required"}), 400
    try:
        tid = int(tenant_id)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    removed = delete_override(tid, str(name))
    metrics_mod.increment("admin.limits.delete", {
        "tenant_id": str(tid),
        "name": str(name),
        "removed": "true" if removed else "false",
        "actor_role": str(session.get("role")) if "session" in globals() else "unknown",
    })
    return jsonify({"ok": True, "removed": removed})
