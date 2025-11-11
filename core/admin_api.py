from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, jsonify, request, session

from core.auth import require_roles

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
            raw_list.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "active": t.active,
                    "kind": meta.kind if meta else None,
                    "description": meta.description if meta else None,
                    "features": [f.name for f in feats],
                }
            )
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
@require_roles("superuser", "admin")
def toggle_feature() -> FeatureToggleResponse | ErrorResponse:
    from flask import session

    data = request.get_json(silent=True) or {}
    feature = data.get("feature")
    enabled = data.get("enabled")
    target_tenant_id = (
        data.get("tenant_id") if session.get("role") == "superuser" else session.get("tenant_id")
    )
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
@require_roles("superuser", "admin")
def tenant_feature_flag_toggle() -> FeatureToggleResponse | ErrorResponse:
    from flask import session

    data = request.get_json(silent=True) or {}
    raw_name = data.get("name")
    enabled = data.get("enabled")
    if raw_name is None or enabled is None:
        return jsonify(
            {"error": "validation_error", "message": "name and enabled required", "ok": False}
        ), 400  # type: ignore[return-value]
    name = str(raw_name).strip()
    if not name:
        return jsonify({"error": "validation_error", "message": "name empty", "ok": False}), 400  # type: ignore[return-value]
    role = session.get("role")
    target_tenant_id = data.get("tenant_id") if role == "superuser" else session.get("tenant_id")
    if not target_tenant_id:
        return jsonify(
            {"error": "validation_error", "message": "tenant context missing", "ok": False}
        ), 400  # type: ignore[return-value]
    try:
        tid = int(target_tenant_id)
    except Exception:
        return jsonify(
            {"error": "validation_error", "message": "invalid tenant_id", "ok": False}
        ), 400  # type: ignore[return-value]
    svc: FeatureService = current_app.feature_service  # type: ignore[attr-defined]
    if bool(enabled):
        svc.enable(tid, name)
    else:
        svc.disable(tid, name)
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return cast(
            FeatureToggleResponse,
            {
                "ok": True,
                "tenant_id": tid,
                "feature": name,
                "enabled": bool(enabled),
                "features": [f.name for f in feats],
            },
        )
    finally:
        db.close()


@bp.get("/feature_flags")
@require_roles("superuser", "admin")
def tenant_feature_flags_list() -> FeatureToggleResponse | ErrorResponse:
    from flask import session

    role = session.get("role")
    if role == "superuser":
        q_tid = request.args.get("tenant_id") or session.get("tenant_id")
    else:
        q_tid = session.get("tenant_id")
    if not q_tid:
        return jsonify(
            {"error": "validation_error", "message": "tenant context missing", "ok": False}
        ), 400  # type: ignore[return-value]
    try:
        tid = int(q_tid)
    except Exception:
        return jsonify(
            {"error": "validation_error", "message": "invalid tenant_id", "ok": False}
        ), 400  # type: ignore[return-value]
    db = get_session()
    try:
        feats = db.query(TenantFeatureFlag).filter_by(tenant_id=tid, enabled=True).all()
        return cast(
            FeatureToggleResponse,
            {"ok": True, "tenant_id": tid, "features": [f.name for f in feats]},
        )
    finally:
        db.close()


# --- Legacy cook flag usage listing ---
@bp.get("/flags/legacy-cook")
@require_roles("admin")
def list_legacy_cook_tenants() -> (
    TenantListResponse | ErrorResponse
):  # pragma: no cover (covered via dedicated tests)
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
                db.query(TenantFeatureFlag.name).filter_by(tenant_id=t.id, enabled=True).all()
            )
            out.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "active": t.active,
                    "features": [f[0] for f in feats_enabled],
                }
            )
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
            return jsonify(
                {"ok": False, "error": "bad_request", "message": "invalid tenant_id"}
            ), 400
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
            assert src in ("tenant", "default", "fallback")
            items.append(
                {"name": n, "quota": ld["quota"], "per_seconds": ld["per_seconds"], "source": src}
            )
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
                    assert src in ("tenant", "default", "fallback")
                    items.append(
                        {
                            "name": name_filter,
                            "quota": ld["quota"],
                            "per_seconds": ld["per_seconds"],
                            "source": src,
                            "tenant_id": tenant_id,
                        }
                    )
                return jsonify(make_page_response(items, page_req, len(items)))
        for n in sorted(union_names):
            ld, src = get_limit(tenant_id, n)
            if src == "fallback":
                continue  # hide fallback noise in union listing
            assert src in ("tenant", "default", "fallback")
            row: LimitView = {
                "name": n,
                "quota": ld["quota"],
                "per_seconds": ld["per_seconds"],
                "source": src,
                "tenant_id": tenant_id,
            }
            items.append(row)
    total = len(items)
    start = (page_req["page"] - 1) * page_req["size"]
    page_slice = items[start : start + page_req["size"]]
    return jsonify(make_page_response(page_slice, page_req, total))


@bp.post("/limits")
@require_roles("admin")
@http_limit(
    name="admin_limits_write",
    key_func=lambda: f"{session.get('tenant_id')}:{session.get('user_id')}",  # type: ignore[arg-type]
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
        return jsonify(
            {
                "ok": False,
                "error": "bad_request",
                "message": "tenant_id,name,quota,per_seconds required",
            }
        ), 400
    try:
        tid = int(tenant_id)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    try:
        q = int(quota)
        p = int(per_seconds)
    except Exception:
        return jsonify(
            {"ok": False, "error": "bad_request", "message": "invalid quota/per_seconds"}
        ), 400
    # clamp via registry helper
    ld_before, src_before = get_limit(tid, str(name))
    set_override(tid, str(name), q, p)
    ld_after, src_after = get_limit(tid, str(name))
    updated = not (ld_before == ld_after and src_before == src_after)
    metrics_mod.increment(
        "admin.limits.upsert",
        {
            "tenant_id": str(tid),
            "name": str(name),
            "updated": "true" if updated else "false",
            "actor_role": str(session.get("role")),
        },
    )
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
            actor_role=session.get("role"),  # type: ignore[arg-type]
        )
    return jsonify(
        {
            "ok": True,
            "item": {
                "tenant_id": tid,
                "name": str(name),
                "quota": ld_after["quota"],
                "per_seconds": ld_after["per_seconds"],
                "source": src_after,
            },
            "updated": updated,
        }
    )


@bp.delete("/limits")
@require_roles("admin")
@http_limit(
    name="admin_limits_write",
    key_func=lambda: f"{session.get('tenant_id')}:{session.get('user_id')}",  # type: ignore[arg-type]
    feature_flag="rate_limit_admin_limits_write",
    use_registry=True,
)
def delete_limit():  # type: ignore[return-value]
    from flask import session

    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or session.get("tenant_id")
    name = data.get("name")  # limit identifier
    if tenant_id is None or name is None:
        return jsonify(
            {"ok": False, "error": "bad_request", "message": "tenant_id,name required"}
        ), 400
    try:
        tid = int(tenant_id)
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    removed = delete_override(tid, str(name))
    metrics_mod.increment(
        "admin.limits.delete",
        {
            "tenant_id": str(tid),
            "name": str(name),
            "removed": "true" if removed else "false",
            "actor_role": str(session.get("role")),
        },
    )
    from contextlib import suppress as _suppress

    with _suppress(Exception):  # pragma: no cover - audit non-critical
        _emit_audit(
            "limits_delete",
            tenant_id=tid,
            limit_name=str(name),
            removed=removed,
            actor_user_id=session.get("user_id"),  # type: ignore[arg-type]
            actor_role=session.get("role"),  # type: ignore[arg-type]
        )
    return jsonify({"ok": True, "removed": removed})


# ============================================================================
# Admin Module - Phase A API Endpoints
# ============================================================================

from .http_errors import bad_request, forbidden, not_found, problem
from .admin_service import AdminService
from .etag import ConcurrencyError, make_collection_etag, make_etag
from .db import get_session
from sqlalchemy import text


def _admin_feature_enabled(name: str) -> bool:
    """Check if admin feature flag is enabled for current tenant."""
    try:
        # Check tenant-specific feature flags first (via g.tenant_feature_flags if set)
        from flask import g
        override = getattr(g, "tenant_feature_flags", {}).get(name)
        if override is not None:
            return bool(override)
        
        # Fall back to global feature registry
        reg = getattr(current_app, "feature_registry", None)
        if reg is not None:
            return bool(reg.enabled(name))
    except Exception:
        pass
    return False


def _require_admin_module_enabled():
    """Return 404 ProblemDetails if admin module is disabled."""
    if not _admin_feature_enabled("ff.admin.enabled"):
        return not_found(
            error_type="admin_disabled",
            detail="Admin module is not enabled",
        )
    return None


def _admin_tenant_id():
    """Get current tenant ID from session."""
    tid = session.get("tenant_id")
    if not tid:
        # In tests, this should be set via header injector; treat missing as 401
        return None
    return tid


def _validate_week_range(week: int) -> bool:
    """Validate week number is in valid range 1-53."""
    return 1 <= week <= 53


@bp.get("/stats")
@require_roles("admin", "editor")
def get_admin_stats():
    """Get system statistics (admin/editor access only).
    
    Phase A: Returns minimal statistics with ETag.
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    
    tid = _admin_tenant_id()
    if not tid:
        return forbidden("tenant_required", "Tenant context required")
    
    # Parse query parameters
    try:
        year = request.args.get("year", type=int)
        week = request.args.get("week", type=int) 
        department_id = request.args.get("department_id")
        
        # Validation
        if year is not None and (year < 1970 or year > 2100):
            return bad_request("Year must be between 1970 and 2100")
        
        if week is not None and not _validate_week_range(week):
            return bad_request("Week must be between 1 and 53")
        
        # Default to current year/week if not provided (Phase A: use fixed values)
        if year is None:
            year = 2025
        if week is None:
            week = 45
        
        # Phase A: Minimal stats payload
        stats = {
            "year": year,
            "week": week,
            "departments": []
        }
        
        # Generate weak ETag for caching
        etag = f'W/"admin:stats:y{year}:w{week}:v0"'
        
        # Check If-None-Match for 304 Not Modified
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            from flask import Response
            response = Response(status=304)
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
            return response
        
        response = jsonify(stats)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return response
        
    except Exception as e:
        return bad_request(f"Invalid request parameters: {str(e)}")


@bp.post("/sites")
@require_roles("admin")
def create_site():
    """Create new site (admin only)."""
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("name is required")
    svc = AdminService()
    try:
        rec, etag = svc.create_site(name)
    except Exception as e:  # pragma: no cover – unexpected
        return bad_request(str(e))
    resp = jsonify(rec)
    resp.status_code = 201
    resp.headers["ETag"] = etag
    return resp


@bp.post("/departments")
@require_roles("admin")
def create_department():
    """Create new department (admin only)."""
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    data = request.get_json(silent=True) or {}
    site_id = data.get("site_id")
    name = (data.get("name") or "").strip()
    mode = data.get("resident_count_mode") or "fixed"
    fixed = data.get("resident_count_fixed")
    if not site_id or not name:
        return bad_request("site_id and name are required")
    svc = AdminService()
    try:
        rec, etag = svc.create_department(site_id, name, mode, fixed)
    except ValueError as ve:
        return bad_request(str(ve))
    resp = jsonify(rec)
    resp.status_code = 201
    resp.headers["ETag"] = etag
    return resp


@bp.put("/departments/<department_id>")
@require_roles("admin")
def update_department(department_id: str):
    """Update department (admin only, requires If-Match)."""
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
    svc = AdminService()
    try:
        rep, etag = svc.update_department(department_id, if_match, data)
    except ValueError as ve:
        return bad_request(str(ve))
    except ConcurrencyError:
        # Return 412 with ProblemDetails and current ETag
        current = AdminService().get_department_current_etag(department_id)
        pb = problem(412, "etag_mismatch", "Precondition Failed", "Resource has been modified since last read")
        # Attach current_etag if available
        try:
            body = pb.get_json()
            if current:
                body["current_etag"] = current
            from flask import Response
            resp = jsonify(body)
            return resp, 412
        except Exception:
            return pb
    except Exception as e:  # pragma: no cover – staging diagnostics
        # Return problem+json with error detail to aid staging debugging instead of generic 500
        try:
            return problem(500, "internal_error", "Internal Server Error", detail=str(e))
        except Exception:
            raise
    resp = jsonify(rep)
    resp.headers["ETag"] = etag
    return resp


@bp.put("/departments/<department_id>/notes")
@require_roles("admin")
def update_department_notes(department_id: str):
    """Update department notes (admin only, requires If-Match)."""
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
    notes = data.get("notes")
    svc = AdminService()
    try:
        rep, etag = svc.update_department_notes(department_id, if_match, notes)
    except ValueError as ve:
        return bad_request(str(ve))
    except ConcurrencyError:
        current = AdminService().get_department_current_etag(department_id)
        pb = problem(412, "etag_mismatch", "Precondition Failed", "Resource has been modified since last read")
        try:
            body = pb.get_json()
            if current:
                body["current_etag"] = current
            resp = jsonify(body)
            return resp, 412
        except Exception:
            return pb
    resp = jsonify(rep)
    resp.headers["ETag"] = etag
    return resp


@bp.put("/departments/<department_id>/diet-defaults")
@require_roles("admin")
def update_diet_defaults(department_id: str):
    """Update dietary defaults for department (admin only, requires If-Match)."""
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
    items = data.get("items") or data.get("dietary_counts") or []
    if not isinstance(items, list):
        return bad_request("invalid items")
    svc = AdminService()
    try:
        items_out, etag = svc.update_diet_defaults(department_id, if_match, items)
    except ValueError as ve:
        return bad_request(str(ve))
    except ConcurrencyError:
        current = AdminService().get_department_current_etag(department_id)
        pb = problem(412, "etag_mismatch", "Precondition Failed", "Resource has been modified since last read")
        try:
            body = pb.get_json()
            if current:
                body["current_etag"] = current
            resp = jsonify(body)
            return resp, 412
        except Exception:
            return pb
    resp = jsonify({"department_id": department_id, "items": items_out})
    resp.headers["ETag"] = etag
    return resp


@bp.post("/menu-import")
@require_roles("admin")
def start_menu_import():
    """Start menu import job (admin only).
    
    Phase A: Returns 501 Not Implemented.
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    # Basic validation to satisfy tests: require minimal body fields
    data = request.get_json(silent=True) or {}
    if not data.get("data_format") or not data.get("data"):
        return bad_request("missing required fields: data_format, data")
    return problem(501, "not_implemented_phase_a", "Not Implemented", "Menu import will be implemented in Phase B")


@bp.get("/menu-import/<job_id>")
@require_roles("admin", "editor")
def get_menu_import_status(job_id: str):
    """Get menu import job status (admin/editor access).
    
    Phase A: Returns 501 Not Implemented.
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    
    return problem(501, "not_implemented_phase_a", "Not Implemented", "Menu import status tracking will be implemented in Phase B")


@bp.put("/alt2")
@require_roles("admin")
def update_bulk_alt2():
    """Bulk Alt2 configuration (admin only, requires If-Match).

    Body: { week:int, items:[{department_id, weekday, enabled}] }
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
    try:
        week = int(data.get("week"))
    except Exception:
        return bad_request("invalid week")
    if not _validate_week_range(week):
        return bad_request("Week must be between 1 and 53")
    items = data.get("items") or []
    if not isinstance(items, list):
        return bad_request("items must be list")
    svc = AdminService()
    try:
        body, new_etag = svc.update_alt2_bulk(if_match, week, items)
    except ValueError as ve:
        return bad_request(str(ve))
    except ConcurrencyError:
        current = AdminService().get_alt2_collection_etag(week)
        pb = problem(412, "etag_mismatch", "Precondition Failed", "Resource has been modified since last read")
        try:
            body = pb.get_json()
            body["current_etag"] = current
            resp = jsonify(body)
            return resp, 412
        except Exception:
            return pb
    resp = jsonify(body)
    resp.headers["ETag"] = new_etag
    return resp


# ============================================================================
# Phase D – Conditional GET Endpoints (If-None-Match / 304)
# ============================================================================

def _none_match_matches(header_val: str | None, current_etag: str) -> bool:
    """Return True if any ETag token in If-None-Match matches current_etag.

    Supports simple comma-separated list; whitespace trimmed. Does not implement * wildcard.
    """
    if not header_val:
        return False
    # Some clients quote tokens already – keep raw compare
    parts = [p.strip() for p in header_val.split(',') if p.strip()]
    return current_etag in parts


def _conditional_response(etag: str, if_none_match: str | None, payload_builder):
    """Return 304 if If-None-Match matches etag, else 200 with JSON payload.

    payload_builder: callable that returns dict body.
    """
    if _none_match_matches(if_none_match, etag):
        from flask import Response
        r = Response(status=304)
        r.headers['ETag'] = etag
        r.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'
        return r
    body = payload_builder()
    resp = jsonify(body)
    resp.headers['ETag'] = etag
    resp.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'
    return resp


@bp.get('/sites')
@require_roles('admin','editor')
def list_sites():
    """List sites for tenant with collection ETag and conditional GET.

    Collection ETag format: W/"admin:sites:tenant:<tenant_id>:v<max>"
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    tid = _admin_tenant_id()
    if not tid:
        return forbidden('tenant_required','Tenant context required')
    svc = AdminService()
    rows = svc.sites_repo.list_sites()
    max_v = max([r.get('version',0) for r in rows], default=0)
    etag = make_collection_etag('admin:sites', f'tenant:{tid}', max_v)
    return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'items': rows})


@bp.get('/departments')
@require_roles('admin','editor')
def list_departments():
    """List departments for a site with collection ETag.

    Required query param: site=<site_id>
    ETag: W/"admin:departments:site:<site_id>:v<max>"
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    site_id = request.args.get('site') or request.args.get('site_id')
    if not site_id:
        return bad_request('site query param required')
    svc = AdminService()
    rows = svc.depts_repo.list_for_site(site_id)
    max_v = max([r.get('version',0) for r in rows], default=0)
    etag = make_collection_etag('admin:departments', f'site:{site_id}', max_v)
    return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'site_id': site_id, 'items': rows})


@bp.get('/diet-defaults')
@require_roles('admin','editor')
def get_diet_defaults():
    """Get dietary defaults for department (single resource ETag).

    Query: department=<id>
    Uses department version ETag: existing make_etag("admin","dept",dep_id,version)
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    dept_id = request.args.get('department') or request.args.get('department_id')
    if not dept_id:
        return bad_request('department query param required')
    svc = AdminService()
    items = svc.diet_repo.list_for_department(dept_id)
    version = svc.depts_repo.get_version(dept_id) or 0
    etag = make_etag('admin','dept', dept_id, version)
    return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'department_id': dept_id, 'items': items})


@bp.get('/alt2')
@require_roles('admin','editor')
def get_alt2_week():
    """Get alt2 flags for a week (collection ETag).

    Query: week=<int>
    ETag: W/"admin:alt2:week:<week>:v<max>"
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    try:
        week = int(request.args.get('week',''))
    except Exception:
        return bad_request('week query param required/int')
    if not _validate_week_range(week):
        return bad_request('Week must be between 1 and 53')
    svc = AdminService()
    rows = svc.alt2_repo.list_for_week(week)
    max_v = max([r.get('version',0) for r in rows], default=0)
    etag = make_collection_etag('admin:alt2', f'week:{week}', max_v)
    simplified = [
        {
            'department_id': r['department_id'],
            'weekday': r['weekday'],
            'enabled': r['enabled']
        } for r in rows
    ]
    return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'week': week, 'items': simplified})


@bp.get('/notes')
@require_roles('admin','editor')
def get_notes_scope():
    """Get notes for site or department scope (Phase D simplified view).

    Query: scope=site|department & site_id|department_id=<id>
    For department: returns {department_id, notes}; ETag department version.
    For site: returns {site_id, notes}; ETag site collection version (or 0).
    """
    maybe = _require_admin_module_enabled()
    if maybe is not None:
        return maybe
    scope = (request.args.get('scope') or '').strip().lower()
    if scope not in {'site','department'}:
        return bad_request('scope must be site or department')
    db = get_session()
    try:
        if scope == 'department':
            dept_id = request.args.get('department_id') or request.args.get('department')
            if not dept_id:
                return bad_request('department_id required')
            row = db.execute(text('SELECT notes, COALESCE(version,0) FROM departments WHERE id=:id'), {'id': dept_id}).fetchone()
            notes_val = row[0] if row else None
            version = int(row[1]) if row else 0
            etag = make_etag('admin','dept', dept_id, version)
            return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'department_id': dept_id, 'notes': notes_val})
        else:
            site_id = request.args.get('site_id') or request.args.get('site')
            if not site_id:
                return bad_request('site_id required')
            row = db.execute(text('SELECT notes, COALESCE(version,0) FROM sites WHERE id=:id'), {'id': site_id}).fetchone()
            notes_val = row[0] if row else None
            version = int(row[1]) if row else 0
            etag = make_etag('admin','site', site_id, version)
            return _conditional_response(etag, request.headers.get('If-None-Match'), lambda: {'site_id': site_id, 'notes': notes_val})
    finally:
        db.close()
