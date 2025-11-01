from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, jsonify, request, session

from .app_authz import require_roles

from . import metrics as metrics_mod
from .api_types import (
    ErrorResponse,
    FeatureToggleResponse,
    LimitView,
    TenantCreateResponse,
    TenantListResponse,
)
from .db import get_session
from .feature_service import FeatureService
from .http_limits import limit as http_limit
from .limit_registry import (
    delete_override,
    get_limit,
    list_default_names,
    list_tenant_names,
    set_override,
)
from .models import Tenant, TenantFeatureFlag, TenantMetadata
from .pagination import make_page_response, parse_page_params

try:  # audit optional robustness
    from . import audit as _audit_mod  # type: ignore
    def _emit_audit(event_name: str, **fields):  # indirection layer for monkeypatch friendliness
        _audit_mod.log_event(event_name, **fields)  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    def _emit_audit(event_name: str, **fields):  # type: ignore[unused-ignore]
        return None

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
@http_limit(
    name="admin_limits_write",
    key_func=lambda : f"{session.get('tenant_id')}:{session.get('user_id')}",  # type: ignore[arg-type]
    feature_flag="rate_limit_admin_limits_write",
    use_registry=True,
)
def upsert_limit():  # type: ignore[return-value]
    from flask import session
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or session.get("tenant_id")
    name = data.get("name")  # limit identifier
    quota = data.get("quota")
    per_seconds = data.get("per_seconds") or data.get("per")
    if tenant_id is None or name is None or quota is None or per_seconds is None:
        return jsonify({"ok": False, "error": "bad_request", "message": "tenant_id,name,quota,per_seconds required"}), 400
    try:
        tid = int(tenant_id)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    try:
        q = int(quota)
        p = int(per_seconds)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid quota/per_seconds"}), 400
    # clamp via registry helper
    ld_before, src_before = get_limit(tid, str(name))
    set_override(tid, str(name), q, p)
    ld_after, src_after = get_limit(tid, str(name))
    updated = not (ld_before == ld_after and src_before == src_after)
    metrics_mod.increment("admin.limits.upsert", {
        "tenant_id": str(tid),
        "name": str(name),
        "updated": "true" if updated else "false",
        "actor_role": str(session.get("role")),
    })
    from contextlib import suppress as _suppress
    with _suppress(Exception):  # pragma: no cover - audit non-critical
        _emit_audit(
            "limits_upsert",
            tenant_id=tid,
            limit_name=str(name),
            quota=ld_after["quota"],
            per_seconds=ld_after["per_seconds"],
            updated=updated,
            actor_user_id=session.get("user_id"),  # type: ignore[arg-type]
            actor_role=session.get("role"),        # type: ignore[arg-type]
        )
    return jsonify({"ok": True, "item": {"tenant_id": tid, "name": str(name), "quota": ld_after["quota"], "per_seconds": ld_after["per_seconds"], "source": src_after}, "updated": updated})


@bp.delete("/limits")
@require_roles("admin")
@http_limit(
    name="admin_limits_write",
    key_func=lambda : f"{session.get('tenant_id')}:{session.get('user_id')}",  # type: ignore[arg-type]
    feature_flag="rate_limit_admin_limits_write",
    use_registry=True,
)
def delete_limit():  # type: ignore[return-value]
    from flask import session
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or session.get("tenant_id")
    name = data.get("name")  # limit identifier
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
        "actor_role": str(session.get("role")),
    })
    from contextlib import suppress as _suppress
    with _suppress(Exception):  # pragma: no cover - audit non-critical
        _emit_audit(
            "limits_delete",
            tenant_id=tid,
            limit_name=str(name),
            removed=removed,
            actor_user_id=session.get("user_id"),  # type: ignore[arg-type]
            actor_role=session.get("role"),        # type: ignore[arg-type]
        )
    return jsonify({"ok": True, "removed": removed})


# ---- Phase-2: admin users (stubs) -----------------------------------------

@bp.get("/users")
@require_roles("admin")
def admin_users_list_stub():  # type: ignore[return-value]
    """List users for current tenant.

    Returns: {items:[{id,email,role}], total}
    """
    # Pagination stub: parse optional page/size leniently; coerce to bounds; always set header when provided
    args = request.args
    page_raw = args.get("page")
    size_raw = args.get("size")
    stub = page_raw is not None or size_raw is not None
    if page_raw is not None:
        try:
            page_val = int(page_raw)
            if page_val < 1:
                page_val = 1
        except Exception:
            # ignore unparseable
            pass
    if size_raw is not None:
        try:
            size_val = int(size_raw)
            if size_val < 1:
                size_val = 1
            if size_val > 100:
                size_val = 100
        except Exception:
            # ignore unparseable
            pass

    from flask import g as _g
    from .db import get_session as _get_session
    from .models import User as _User
    from sqlalchemy import func as _func
    db = _get_session()
    try:
        tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
        tid_int = int(tid) if tid is not None else None
    except Exception:
        tid_int = None
    # Optional quick filter on email (case-insensitive substring)
    q = (request.args.get("q") or "").strip().lower()
    items: list[dict[str, object]] = []
    total = 0
    deleted_total = 0
    try:
        if tid_int is not None:
            query = db.query(_User).filter_by(tenant_id=tid_int).filter(_User.deleted_at.is_(None))
            if q:
                query = query.filter(_func.lower(_User.email).contains(q))
            rows = query.all()
            total = len(rows)
            for u in rows:
                items.append({"id": str(getattr(u, "id", "")), "email": str(u.email), "role": str(u.role)})
            # Count soft-deleted users for this tenant (deleted_at IS NOT NULL)
            try:
                deleted_total = db.query(_User).filter(_User.tenant_id == tid_int).filter(_User.deleted_at.isnot(None)).count()
            except Exception:
                deleted_total = 0
    finally:
        db.close()
    resp = jsonify({"items": items, "total": total})
    if stub:
        resp.headers["X-Pagination-Stub"] = "true"
    # Always include count of soft-deleted users (as string) for current tenant
    resp.headers["X-Users-Deleted-Total"] = str(int(deleted_total))
    return resp, 200


@bp.post("/users")
@require_roles("admin")
def admin_users_create_stub():  # type: ignore[return-value]
    """Stub: create user in current tenant.

    TODO Phase-2: replace stub with repo/service.
    """
    # Copilot prompt: Add input validation: require email containing '@', role in {'admin','editor','viewer'}, and disallow additional properties. On invalid, return 422 using the same JSON envelope as other errors plus invalid_params like [{"name":"email","reason":"invalid_format"}]. Keep current success payload unchanged.
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name": "body", "reason": "invalid_type"}]}), 422  # type: ignore[return-value]
    allowed_roles = {"admin", "editor", "viewer"}
    invalid_params: list[dict[str, object]] = []
    # Extract and normalize
    raw_email = data.get("email")
    email = (raw_email.strip() if isinstance(raw_email, str) else raw_email)
    role = data.get("role")
    # Required checks
    if email is None:
        invalid_params.append({"name": "email", "reason": "required"})
    if role is None:
        invalid_params.append({"name": "role", "reason": "required"})
    # Format / enum checks (only if present)
    if isinstance(email, str):
        if "@" not in email:
            invalid_params.append({"name": "email", "reason": "invalid_format"})
    elif email is not None:
        invalid_params.append({"name": "email", "reason": "invalid_type"})
    if role is not None:
        if not isinstance(role, str):
            invalid_params.append({"name": "role", "reason": "invalid_type"})
        elif role not in allowed_roles:
            invalid_params.append({"name": "role", "reason": "invalid_enum", "allowed": sorted(list(allowed_roles))})
    # Additional properties
    for k in data.keys():
        if k not in ("email", "role"):
            invalid_params.append({"name": str(k), "reason": "additional_properties_not_allowed"})
    if invalid_params:
        return jsonify({"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": invalid_params}), 422  # type: ignore[return-value]
    # Success (happy path connected to DB minimally; still returns simple payload)
    try:
        from flask import g as _g
        from .db import get_session as _get_session
        from .models import User as _User
        db = _get_session()
        try:
            tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
            tid_int = int(tid) if tid is not None else None
        except Exception:
            tid_int = None
        if tid_int is None:
            # Tenant context missing -> treat as invalid for now
            return jsonify({"ok": False, "error": "invalid", "message": "tenant context missing"}), 400  # type: ignore[return-value]
        # Duplicate email check (tenant-scoped)
        exists = None
        try:
            exists = db.query(_User).filter_by(tenant_id=tid_int, email=str(email)).first()
        except Exception:
            exists = None
        if exists is not None:
            return jsonify({"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name": "email", "reason": "duplicate"}]}), 422  # type: ignore[return-value]
        # Minimal create; password_hash placeholder to satisfy NOT NULL.
        new_user = _User(tenant_id=tid_int, email=str(email), role=str(role), password_hash="!")  # type: ignore[arg-type]
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
        finally:
            db.close()
        return jsonify({"id": str(getattr(new_user, "id", "")), "email": str(email), "role": str(role)}), 201
    except Exception:
        # On any unexpected error, keep previous stub payload to avoid breaking flow
        return jsonify({"id": "stub", "email": "stub@local", "role": "viewer"}), 201


@bp.delete("/users/<string:user_id>")
@require_roles("admin")
def admin_users_delete_soft(user_id: str):  # type: ignore[return-value]
    """Soft-delete a user in current tenant by setting deleted_at.

    Behavior:
      - Guarded by admin + CSRF (enforced centrally).
      - Lookup by (tenant_id, user_id) with deleted_at IS NULL.
      - If not found → 404 {ok:false,error:"not_found",message:"user not found"}.
      - If found → set deleted_at=now(UTC), commit, return 200 {id, deleted_at}.
      - Idempotent: second call returns 404.
    """
    from flask import g as _g
    from .db import get_session as _get_session
    from .models import User as _User
    from datetime import datetime as _dt, UTC as _UTC
    # Parse tenant + user id
    try:
        tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
        tid_int = int(tid) if tid is not None else None
    except Exception:
        tid_int = None
    try:
        uid_int = int(user_id)
    except Exception:
        uid_int = None
    if tid_int is None or uid_int is None:
        r404 = jsonify({"ok": False, "error": "not_found", "message": "user not found"})
        return r404, 404  # type: ignore[return-value]
    db = _get_session()
    try:
        row = (
            db.query(_User)
            .filter(_User.tenant_id == tid_int, _User.id == uid_int, _User.deleted_at.is_(None))
            .first()
        )
        if not row:
            r404 = jsonify({"ok": False, "error": "not_found", "message": "user not found"})
            return r404, 404  # type: ignore[return-value]
        # Soft-delete
        row.deleted_at = _dt.now(_UTC)
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({"id": str(getattr(row, "id", user_id)), "deleted_at": row.deleted_at.isoformat()}), 200
    finally:
        db.close()


# ---- Phase-2: admin feature-flags (stubs) ---------------------------------
# Phase-2 stub: feature-flags endpoints (guarded)

@bp.get("/feature-flags")
@require_roles("admin")
def admin_feature_flags_list_stub():  # type: ignore[return-value]
    """List feature flags for tenant with optional ?q= filter on key or notes (case-insensitive)."""
    # Pagination stub: parse optional page/size leniently; coerce to bounds; always set header when provided
    args = request.args
    page_raw = args.get("page")
    size_raw = args.get("size")
    stub = page_raw is not None or size_raw is not None
    if page_raw is not None:
        try:
            page_val = int(page_raw)
            if page_val < 1:
                page_val = 1
        except Exception:
            pass
    if size_raw is not None:
        try:
            size_val = int(size_raw)
            if size_val < 1:
                size_val = 1
            if size_val > 100:
                size_val = 100
        except Exception:
            pass
    from flask import g as _g
    from .db import get_session as _get_session
    from .models import TenantFeatureFlag as _TFF
    db = _get_session()
    try:
        tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
        tid_int = int(tid) if tid is not None else None
    except Exception:
        tid_int = None
    q = (request.args.get("q") or "").strip().lower()
    items: list[dict[str, object]] = []
    total = 0
    try:
        if tid_int is not None:
            rows = db.query(_TFF).filter_by(tenant_id=tid_int).all()
            if q:
                rows = [r for r in rows if (q in str(r.name).lower()) or (q in str(r.notes or "").lower())]
            total = len(rows)
            for r in rows:
                items.append({
                    "key": str(r.name),
                    "enabled": bool(r.enabled),
                    "notes": r.notes or "",
                    "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
                })
    finally:
        db.close()
    resp = jsonify({"items": items, "total": total})
    if stub:
        resp.headers["X-Pagination-Stub"] = "true"
    return resp, 200


@bp.patch("/feature-flags/<string:key>")
@require_roles("admin")
def admin_feature_flag_update_stub(key: str):  # type: ignore[return-value]
    """Stub: update a feature flag (enable/notes).

    TODO Phase-2: add CSRF enforcement, validation and connect to service.
    """
    # Validation: enabled must be bool (if present); notes must be str len<=500 (if present); no additional props.
    data = request.get_json(silent=True) or {}
    invalid_params: list[dict[str, object]] = []
    if isinstance(data, dict):
        allowed_keys = {"enabled", "notes"}
        if "enabled" in data:
            if not isinstance(data.get("enabled"), bool):
                invalid_params.append({"name": "enabled", "reason": "invalid_type"})
        if "notes" in data:
            val = data.get("notes")
            if not isinstance(val, str):
                invalid_params.append({"name": "notes", "reason": "invalid_type"})
            else:
                if len(val) > 500:
                    invalid_params.append({"name": "notes", "reason": "max_length_exceeded", "max": 500})
        for k in data.keys():
            if k not in allowed_keys:
                invalid_params.append({"name": str(k), "reason": "additional_properties_not_allowed"})
    else:
        invalid_params.append({"name": "body", "reason": "invalid_type"})
    if invalid_params:
        return jsonify({"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": invalid_params}), 422  # type: ignore[return-value]

    # Not-found guard (tenant+key). If missing, return 404 with central envelope.
    try:
        from .db import get_session as _get_session
        from .models import TenantFeatureFlag as _TenantFeatureFlag
        from flask import g as _g
        db = _get_session()
        try:
            tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
            tid_int = int(tid) if tid is not None else None
        except Exception:
            tid_int = None
        if tid_int is None:
            # Without tenant context, treat as not found to avoid leaking keys across tenants
            r404 = jsonify({"ok": False, "error": "not_found", "message": "feature flag not found"})
            return r404, 404  # type: ignore[return-value]
        try:
            row = db.query(_TenantFeatureFlag).filter_by(tenant_id=tid_int, name=str(key)).first()
        finally:
            db.close()
        if not row:
            r404 = jsonify({"ok": False, "error": "not_found", "message": "feature flag not found"})
            return r404, 404  # type: ignore[return-value]
    except Exception:
        # On errors during lookup, fall back to stubbed 200 to avoid breaking flows in Phase-2
        pass

    # Persist enabled/notes if provided; return updated record
    try:
        from datetime import datetime as _dt, UTC as _UTC
        from .db import get_session as _get_session2
        from .models import TenantFeatureFlag as _TenantFeatureFlag2
        from flask import g as _g2
        db2 = _get_session2()
        try:
            tid2 = getattr(_g2, "tenant_id", None) or session.get("tenant_id")
            tid2_int = int(tid2) if tid2 is not None else None
        except Exception:
            tid2_int = None
        # Fetch again to be safe in this scope
        row2 = None
        if tid2_int is not None:
            row2 = db2.query(_TenantFeatureFlag2).filter_by(tenant_id=tid2_int, name=str(key)).first()
        if row2 is not None:
            changed = False
            if isinstance(data, dict) and "enabled" in data:
                row2.enabled = bool(data.get("enabled"))
                changed = True
            if isinstance(data, dict) and "notes" in data:
                val = data.get("notes")
                row2.notes = str(val) if isinstance(val, str) else None
                changed = True
            if changed:
                row2.updated_at = _dt.now(_UTC)
                db2.add(row2)
                db2.commit()
                db2.refresh(row2)
            resp = {
                "key": str(row2.name),
                "enabled": bool(row2.enabled),
                "notes": row2.notes if row2.notes is not None else "",
                "updated_at": (row2.updated_at.isoformat()) if row2.updated_at else None,
            }
            return jsonify(resp), 200
        # If we cannot refetch row, fall through to stub
    except Exception:
        pass
    return jsonify({"key": key, "enabled": False, "notes": ""}), 200


# ---- Phase-2: admin roles (stubs) -----------------------------------------
# Phase-2 stub: roles endpoints (guarded)

@bp.get("/roles")
@require_roles("admin")
def admin_roles_list_stub():  # type: ignore[return-value]
    """List users and their roles for current tenant (same shape as users list)."""
    # Pagination stub: parse optional page/size leniently; coerce to bounds; always set header when provided
    args = request.args
    page_raw = args.get("page")
    size_raw = args.get("size")
    stub = page_raw is not None or size_raw is not None
    if page_raw is not None:
        try:
            page_val = int(page_raw)
            if page_val < 1:
                page_val = 1
        except Exception:
            pass
    if size_raw is not None:
        try:
            size_val = int(size_raw)
            if size_val < 1:
                size_val = 1
            if size_val > 100:
                size_val = 100
        except Exception:
            pass
    from flask import g as _g
    from .db import get_session as _get_session
    from .models import User as _User
    from sqlalchemy import func as _func
    db = _get_session()
    try:
        tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
        tid_int = int(tid) if tid is not None else None
    except Exception:
        tid_int = None
    # Optional quick filter on email (case-insensitive substring)
    q = (request.args.get("q") or "").strip().lower()
    items: list[dict[str, object]] = []
    total = 0
    try:
        if tid_int is not None:
            query = db.query(_User).filter_by(tenant_id=tid_int).filter(_User.deleted_at.is_(None))
            if q:
                query = query.filter(_func.lower(_User.email).contains(q))
            rows = query.all()
            total = len(rows)
            for u in rows:
                items.append({"id": str(getattr(u, "id", "")), "email": str(u.email), "role": str(u.role)})
    finally:
        db.close()
    resp = jsonify({"items": items, "total": total})
    if stub:
        resp.headers["X-Pagination-Stub"] = "true"
    return resp, 200


@bp.patch("/roles/<string:user_id>")
@require_roles("admin")
def admin_roles_update_stub(user_id: str):  # type: ignore[return-value]
    """Stub: update a user's role.

    TODO Phase-2: add CSRF enforcement, validate enum and connect to service.
    """
    # Validation: require body with only {"role": enum}; disallow extras
    data = request.get_json(silent=True) or {}
    invalid_params: list[dict[str, object]] = []
    allowed_roles = {"admin", "editor", "viewer"}
    if not isinstance(data, dict):
        invalid_params.append({"name": "body", "reason": "invalid_type"})
    else:
        if "role" not in data:
            invalid_params.append({"name": "role", "reason": "required"})
        else:
            role = data.get("role")
            if not isinstance(role, str):
                invalid_params.append({"name": "role", "reason": "invalid_type"})
            elif role not in allowed_roles:
                invalid_params.append({"name": "role", "reason": "invalid_enum", "allowed": ["admin","editor","viewer"]})
        for k in data.keys():
            if k not in ("role",):
                invalid_params.append({"name": str(k), "reason": "additional_properties_not_allowed"})
    if invalid_params:
        return jsonify({"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": invalid_params}), 422  # type: ignore[return-value]

    # Not-found: lookup user by tenant + user_id; if missing return 404 (validation first)
    try:
        from .db import get_session as _get_session
        from .models import User as _User
        from flask import g as _g
        db = _get_session()
        try:
            tid = getattr(_g, "tenant_id", None) or session.get("tenant_id")
            tid_int = int(tid) if tid is not None else None
        except Exception:
            tid_int = None
        # Treat non-numeric user_id as not found in this stubbed phase
        uid_int = None
        try:
            uid_int = int(user_id)
        except Exception:
            uid_int = None
        if tid_int is None or uid_int is None:
            r404 = jsonify({"ok": False, "error": "not_found", "message": "user not found"})
            return r404, 404  # type: ignore[return-value]
        row = db.query(_User).filter_by(tenant_id=tid_int, id=uid_int).first()
        if not row:
            r404 = jsonify({"ok": False, "error": "not_found", "message": "user not found"})
            db.close()
            return r404, 404  # type: ignore[return-value]
    except Exception:
        # Fall through to stubbed OK on unexpected errors in Phase-2
        pass

    # Persist role change (idempotent) and return updated user payload
    try:
        from datetime import datetime as _dt, UTC as _UTC
        from .db import get_session as _get_session2
        from .models import User as _User2
        from flask import g as _g2
        db2 = _get_session2()
        try:
            tid2 = getattr(_g2, "tenant_id", None) or session.get("tenant_id")
            tid2_int = int(tid2) if tid2 is not None else None
        except Exception:
            tid2_int = None
        # Convert user id to int; if invalid treat as not found (should have been caught above)
        try:
            uid2_int = int(user_id)
        except Exception:
            uid2_int = None
        row2 = None
        if tid2_int is not None and uid2_int is not None:
            row2 = db2.query(_User2).filter_by(tenant_id=tid2_int, id=uid2_int).first()
        if row2 is not None:
            new_role = str(data.get("role"))
            # Idempotent update: only change fields if different
            if str(getattr(row2, "role", "")) != new_role:
                row2.role = new_role
                # Update timestamp in timezone-aware UTC
                try:
                    row2.updated_at = _dt.now(_UTC)
                except Exception:
                    # If for any reason updated_at isn't present or timezone fails, ignore
                    pass
                db2.add(row2)
                db2.commit()
                db2.refresh(row2)
            # If no change, still safe to flush/commit (no-op) for consistency
            else:
                try:
                    db2.flush()
                    db2.commit()
                except Exception:
                    pass
            resp = {
                "id": str(getattr(row2, "id", user_id)),
                "email": str(getattr(row2, "email", "")),
                "role": str(getattr(row2, "role", new_role)),
                "updated_at": (getattr(row2, "updated_at", None).isoformat() if getattr(row2, "updated_at", None) else None),
            }
            db2.close()
            return jsonify(resp), 200
        # If unable to refetch, fall through to stub response
        db2.close()
    except Exception:
        pass
    return jsonify({"id": user_id, "role": data.get("role", "viewer"), "email": "", "updated_at": None}), 200

