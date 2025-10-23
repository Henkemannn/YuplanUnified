from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, make_response, request, session
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from .auth import require_roles
from .db import get_session
from .models import AuditEvent, Module, Tenant, TenantFeatureFlag, TenantModule, Unit
from .services import slugify

bp = Blueprint("superuser_api", __name__, url_prefix="/api/superuser")


def _no_store(resp):  # helper to enforce non-caching for sensitive superuser data
    resp.headers["Cache-Control"] = "no-store"
    return resp


_SUMMARY_CACHE: dict[str, tuple[datetime, dict]] = {}
_SUMMARY_TTL_SECONDS = 5


@bp.get("/summary")
@require_roles("superuser")
def summary():
    """Return high level counts for dashboard KPIs.

    modules_active is currently derived from configured default enabled modules.
    In future this may reflect per-tenant module activation state.
    """
    # Lightweight in-memory cache (still no-store to client)
    now = datetime.now(UTC)
    cached = _SUMMARY_CACHE.get("v1")
    if cached and (now - cached[0]).total_seconds() < _SUMMARY_TTL_SECONDS:
        return _no_store(make_response(jsonify(cached[1]), 200))
    db = get_session()
    try:
        tenants_total = db.execute(select(func.count()).select_from(Tenant)).scalar() or 0
        flags_on = db.execute(
            select(func.count()).select_from(TenantFeatureFlag).where(TenantFeatureFlag.enabled.is_(True))
        ).scalar() or 0
    finally:
        db.close()
    # modules_active: simple placeholder using config list length
    modules_cfg = current_app.config.get("DEFAULT_ENABLED_MODULES") or []
    modules_active = len(modules_cfg)
    payload = {
        "tenants_total": tenants_total,
        "modules_active": modules_active,
        "feature_flags_on": flags_on,
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    _SUMMARY_CACHE["v1"] = (now, payload)
    return _no_store(make_response(jsonify(payload), 200))


@bp.get("/events")
@require_roles("superuser")
def events():
    limit = request.args.get("limit", type=int) or 20
    if limit > 100:
        limit = 100
    after_id = request.args.get("after_id", type=int)
    db = get_session()
    try:
        stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if after_id:
            # simplistic pagination: fetch events with id < after_id
            stmt = select(AuditEvent).where(AuditEvent.id < after_id).order_by(AuditEvent.id.desc()).limit(limit)
        rows = list(db.execute(stmt).scalars())
    finally:
        db.close()
    items: list[dict[str, str]] = []
    next_after_id: int | None = None
    for r in rows:
        ev = r.event.upper() if isinstance(r.event, str) else ""
        title = _event_title(r, ev)
        badge = _event_badge(ev, r)
        items.append({
            "id": f"evt_{r.id}",
            "kind": ev,
            "title": title,
            "ts": r.ts.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            "badge": badge,
        })
    if rows:
        next_after_id = rows[-1].id
    payload = {"items": items, "next_after_id": f"evt_{next_after_id}" if next_after_id else None}
    return _no_store(make_response(jsonify(payload), 200))


def _event_title(row: AuditEvent, kind: str) -> str:
    payload: dict = {}
    _rp = getattr(row, "payload", None)
    if isinstance(_rp, dict):
        payload = _rp
    name = payload.get("name") or payload.get("tenant") or payload.get("tenant_name")
    flag = payload.get("flag") or payload.get("feature")
    module = payload.get("module") or payload.get("module_name")
    # Heuristics per spec
    if kind == "TENANT_CREATED" and name:
        return f"Tenant skapad – {name} skapad"
    if kind == "TENANT_UPDATED" and name:
        return f"Tenant uppdaterad – {name} uppdaterad"
    if kind == "FLAG_TOGGLED" and flag is not None:
        state = payload.get("enabled") or payload.get("on") or payload.get("state")
        onoff = "på" if str(state).lower() in ("1", "true", "yes", "on") else "av"
        return f"Flagga ändrad – {flag} {onoff}"
    if kind == "MODULE_INSTALLED" and module:
        return f"Modul installerad – {module} installerad"
    if kind == "MODULE_ENABLED" and module:
        return f"Modul aktiverad – {module} aktiverad"
    # fallback
    return f"Händelse – {kind}" if kind else "Händelse"


def _event_badge(kind: str, row: AuditEvent) -> str:
    if kind.startswith("TENANT_"):
        return "TENANT"
    if kind.startswith("MODULE_"):
        return "MODUL"
    p: dict = {}
    _rp = getattr(row, "payload", None)
    if isinstance(_rp, dict):
        p = _rp
    # If flag in kind or payload name
    if "FLAG" in kind or "flag" in p or "feature" in p:
        return "FLAG"
    return "INFO"


@bp.get("/health")
@require_roles("superuser")
def health():
    # Basic liveness derived from DB query; queue placeholder
    db_status = "OK"
    try:
        db = get_session()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        db_status = "FAIL"
    api_status = "OK"  # If this executes, API layer responded.
    queue_status = "OK"  # Placeholder until we introduce a queue backend.
    payload = {
        "api": api_status,
        "db": db_status,
        "queue": queue_status,
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    return _no_store(make_response(jsonify(payload), 200))


@bp.post("/tenants")
@require_roles("superuser")
def create_tenant():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    slug = data.get("slug") or slugify(name)
    theme = data.get("theme") or "ocean"
    enabled = bool(data.get("enabled", True))
    if not name:
        return jsonify({"title": "Validation error", "detail": "Namn krävs"}), 400
    slug = slugify(slug)
    if not slug:
        return jsonify({"title": "Validation error", "detail": "Ogiltig slug"}), 400
    # Basic theme whitelist to align with Enum('ocean','emerald') in models
    if str(theme) not in {"ocean", "emerald"}:
        return (
            jsonify(
                {
                    "title": "Validation error",
                    "detail": "Ogiltigt tema",
                    "invalid_params": [{"name": "theme", "reason": "unknown"}],
                }
            ),
            400,
        )
    db = get_session()
    tid: int | None = None
    try:
        # Pre-check common duplicates for clearer 400s (still guard with IntegrityError below)
        if db.query(Tenant).filter_by(slug=slug).first():
            return (
                jsonify(
                    {
                        "title": "Validation error",
                        "detail": "Slug upptagen",
                        "invalid_params": [{"name": "slug", "reason": "taken"}],
                    }
                ),
                400,
            )
        if db.query(Tenant).filter_by(name=name).first():
            return (
                jsonify(
                    {
                        "title": "Validation error",
                        "detail": "Namn upptaget",
                        "invalid_params": [{"name": "name", "reason": "taken"}],
                    }
                ),
                400,
            )
        # Set both legacy 'active' and current 'enabled' to keep older DBs happy
        t = Tenant(name=name, slug=slug, theme=theme, active=enabled, enabled=enabled)
        db.add(t)
        db.commit()
        # Capture id before session closes to avoid lazy-load issues
        tid = int(getattr(t, "id", 0) or 0)
    except IntegrityError as ie:  # fallback for race conditions/unknown unique constraint
        db.rollback()
        # Best-effort mapping of constraint to field
        msg = str(getattr(ie, "orig", ie)).lower()
        invalid = []
        if "slug" in msg:
            invalid.append({"name": "slug", "reason": "taken"})
        if "name" in msg:
            invalid.append({"name": "name", "reason": "taken"})
        return (
            jsonify(
                {
                    "title": "Validation error",
                    "detail": f"Unikhetsfel: {msg}" if msg else "Unikhetsfel",
                    "invalid_params": invalid or [{"name": "_", "reason": "conflict"}],
                }
            ),
            400,
        )
    except Exception as ex:
        db.rollback()
        # In TESTING mode, expose the exception string to aid local debugging
        try:
            if current_app and current_app.config.get("TESTING"):
                return (
                    jsonify(
                        {
                            "title": "Validation error",
                            "detail": f"Exception: {str(ex)}",
                            "invalid_params": [],
                        }
                    ),
                    400,
                )
        except Exception:
            pass
        # Otherwise let the global handler turn this into a Problem 500
        raise
    finally:
        db.close()
    try:
        from .audit_events import record_audit_event

        # Best-effort audit; do not fail tenant creation if audit sink has issues
        record_audit_event(
            "TENANT_CREATED", actor_user_id=session.get("user_id"), tenant_id=tid, name=name, slug=slug
        )
    except Exception:
        pass
    return jsonify({"id": tid, "slug": slug}), 201


@bp.route("/tenants/<int:tid>/org-units", methods=["GET", "POST"])
@require_roles("superuser")
def org_units(tid: int):
    if request.method == "GET":
        db = get_session()
        try:
            rows = db.query(Unit).filter_by(tenant_id=tid).order_by(Unit.id).all()
            items = [{
                "id": u.id,
                "name": u.name,
                "type": getattr(u, "unit_type", None),
                "slug": getattr(u, "slug", None),
                "default_attendance": u.default_attendance,
            } for u in rows]
            return _no_store(make_response(jsonify({"items": items}), 200))
        finally:
            db.close()
    j = request.get_json(force=True)
    name = (j.get("name") or "").strip()
    if not name or len(name) > 80:
        return jsonify({"title": "Validation error", "detail": "Ogiltigt namn", "invalid_params": [{"name": "name", "reason": "length"}]}), 400
    utype = (j.get("type") or "kitchen").strip().lower()
    if utype not in {"kitchen", "department"}:
        return jsonify({"title": "Validation error", "detail": "Ogiltig typ", "invalid_params": [{"name": "type", "reason": "unknown"}]}), 400
    raw_slug = (j.get("slug") or name)
    uslug = slugify(raw_slug) if raw_slug else None
    db = get_session()
    try:
        if uslug:
            existing = db.query(Unit).filter_by(tenant_id=tid, slug=uslug).first()
            if existing:
                return jsonify({"title": "Validation error", "detail": "Slug upptagen", "invalid_params": [{"name": "slug", "reason": "taken"}]}), 400
        u = Unit(tenant_id=tid, name=name, unit_type=utype, slug=uslug, default_attendance=j.get("default_attendance"))
        db.add(u)
        db.commit()
        uid = int(getattr(u, "id", 0) or 0)
    finally:
        db.close()
    try:
        from .audit_events import record_audit_event
        record_audit_event(
            "ORG_UNIT_CREATED",
            actor_user_id=session.get("user_id"),
            tenant_id=tid,
            unit_id=uid,
            name=name,
            type=utype,
        )
    except Exception:
        pass
    return jsonify({"id": uid, "name": name, "type": utype, "slug": uslug, "default_attendance": j.get("default_attendance")}), 201


@bp.patch("/tenants/<int:tid>/org-units/<int:uid>")
@require_roles("superuser")
def org_unit_update(tid: int, uid: int):
    """Rename or change type for an org unit. Auto-updates slug if name/slug provided.

    Body: { name?: str(1-80), type?: 'kitchen'|'department', slug?: str }
    Returns 200 with updated item.
    """
    j = request.get_json(force=True) or {}
    name = (j.get("name") or "").strip()
    utype = (j.get("type") or "").strip().lower() if j.get("type") is not None else None
    raw_slug = j.get("slug")
    if name and len(name) > 80:
        return (
            jsonify({
                "title": "Validation error",
                "detail": "Ogiltigt namn",
                "invalid_params": [{"name": "name", "reason": "length"}],
            }),
            400,
        )
    if utype is not None and utype not in {"kitchen", "department"}:
        return (
            jsonify({
                "title": "Validation error",
                "detail": "Ogiltig typ",
                "invalid_params": [{"name": "type", "reason": "unknown"}],
            }),
            400,
        )
    db = get_session()
    try:
        u = db.query(Unit).filter_by(id=uid, tenant_id=tid).first()
        if not u:
            return jsonify({"title": "Not Found", "detail": "Org-enhet saknas"}), 404
        # Determine new slug
        new_slug = None
        if raw_slug is not None:
            new_slug = slugify(str(raw_slug)) or None
        elif name:
            new_slug = slugify(name) or None
        # Validate slug uniqueness if changed
        if new_slug is not None and new_slug != getattr(u, "slug", None):
            existing = db.query(Unit).filter_by(tenant_id=tid, slug=new_slug).first()
            if existing and int(getattr(existing, "id", 0)) != int(uid):
                return (
                    jsonify({
                        "title": "Validation error",
                        "detail": "Slug upptagen",
                        "invalid_params": [{"name": "slug", "reason": "taken"}],
                    }),
                    400,
                )
        # Apply updates
        if name:
            u.name = name
        if utype is not None:
            u.unit_type = utype
        if new_slug is not None:
            u.slug = new_slug
        db.commit()
        item = {
            "id": u.id,
            "name": u.name,
            "type": getattr(u, "unit_type", None),
            "slug": getattr(u, "slug", None),
            "default_attendance": u.default_attendance,
        }
    finally:
        db.close()
    # Audit best-effort
    try:
        from .audit_events import record_audit_event

        record_audit_event(
            "ORG_UNIT_UPDATED",
            actor_user_id=session.get("user_id"),
            tenant_id=tid,
            unit_id=uid,
            name=item["name"],
            type=item["type"],
            slug=item["slug"],
        )
    except Exception:
        pass
    return jsonify(item), 200


@bp.delete("/tenants/<int:tid>/org-units/<int:uid>")
@require_roles("superuser")
def org_unit_delete(tid: int, uid: int):
    db = get_session()
    deleted = False
    name = None
    try:
        u = db.query(Unit).filter_by(id=uid, tenant_id=tid).first()
        if not u:
            return jsonify({"title": "Not Found", "detail": "Org-enhet saknas"}), 404
        name = getattr(u, "name", None)
        db.delete(u)
        db.commit()
        deleted = True
    finally:
        db.close()
    try:
        if deleted:
            from .audit_events import record_audit_event

            record_audit_event(
                "ORG_UNIT_DELETED",
                actor_user_id=session.get("user_id"),
                tenant_id=tid,
                unit_id=uid,
                name=name,
            )
    except Exception:
        pass
    return ("", 204)


@bp.get("/tenants")
@require_roles("superuser")
def tenants_list():
    """List tenants with optional case-insensitive name filter via ?query=.

    Response: { items: [{id,name,slug,theme,enabled}] }
    """
    q = (request.args.get("query") or "").strip()
    db = get_session()
    try:
        stmt = select(Tenant)
        if q:
            # ilike for case-insensitive substring match
            stmt = stmt.where(Tenant.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(Tenant.name.asc())
        rows = list(db.execute(stmt).scalars())
        items = [
            {
                "id": t.id,
                "name": t.name,
                "slug": getattr(t, "slug", None),
                "theme": getattr(t, "theme", None),
                "enabled": bool(getattr(t, "enabled", True)),
            }
            for t in rows
        ]
        resp = make_response(jsonify({"items": items}), 200)
        return _no_store(resp)
    finally:
        db.close()


@bp.get("/tenants/<int:tid>/modules")
@require_roles("superuser")
def tenant_modules_list(tid: int):
    db = get_session()
    try:
        t = db.query(Tenant).filter(Tenant.id == tid).first()
        if not t:
            return jsonify({"title": "Not Found", "detail": "Tenant saknas"}), 404
        # Left join modules with tenant_modules to compute enabled
        # We'll fetch modules and overlay tenant overrides
        mods = {m.key: m for m in db.query(Module).order_by(Module.name.asc()).all()}
        tmods = {row.module_key: bool(row.enabled) for row in db.query(TenantModule).filter(TenantModule.tenant_id == tid).all()}
        items = [
            {"key": k, "name": getattr(m, "name", k.title()), "enabled": bool(tmods.get(k, False))}
            for k, m in mods.items()
        ]
        resp = make_response(jsonify({"items": items}), 200)
        return _no_store(resp)
    finally:
        db.close()


@bp.post("/tenants/<int:tid>/modules/toggle")
@require_roles("superuser")
def tenant_modules_toggle(tid: int):
    j = request.get_json(force=True) or {}
    key = (j.get("module_key") or "").strip()
    if not key:
        return jsonify({"title": "Validation error", "detail": "module_key krävs"}), 400
    db = get_session()
    enabled = False
    try:
        t = db.query(Tenant).filter(Tenant.id == tid).first()
        if not t:
            return jsonify({"title": "Not Found", "detail": "Tenant saknas"}), 404
        m = db.query(Module).filter(Module.key == key).first()
        if not m:
            return jsonify({"title": "Validation error", "detail": "Okänd modul"}), 400
        row = db.query(TenantModule).filter(TenantModule.tenant_id == tid, TenantModule.module_key == key).first()
        if row is None:
            row = TenantModule(tenant_id=tid, module_key=key, enabled=True)
            db.add(row)
            enabled = True
        else:
            row.enabled = not bool(row.enabled)
            enabled = bool(row.enabled)
        db.commit()
    finally:
        db.close()
    # Audit best-effort
    try:
        from .audit_events import record_audit_event

        record_audit_event(
            "MODULE_ENABLED" if enabled else "MODULE_DISABLED",
            actor_user_id=session.get("user_id"),
            tenant_id=tid,
            module=key,
            enabled=enabled,
        )
    except Exception:
        pass
    return _no_store(make_response(jsonify({"key": key, "enabled": enabled}), 200))

__all__ = ["bp"]
 
 
@bp.get("/feature-flags")
@require_roles("superuser")
def feature_flags_list():
    """List effective feature flags for current tenant context.

    Combines global registry defaults with per-tenant overrides (if any).
    Response: { items: [{key, enabled}] }
    """
    # Registry defaults
    try:
        registry = current_app.feature_registry
    except Exception:
        registry = None
    base: list[dict] = []
    try:
        if registry is not None:
            base = list(registry.list())  # [{'name','enabled','mode'}]
    except Exception:
        base = []
    # Tenant overrides
    tid = session.get("tenant_id")
    overrides: dict[str, bool] = {}
    if tid:
        db = get_session()
        try:
            rows = db.query(TenantFeatureFlag).filter(TenantFeatureFlag.tenant_id == int(tid)).all()
            overrides = {r.name: bool(r.enabled) for r in rows}
        finally:
            db.close()
    items = []
    for d in base:
        key = d.get("name")
        if not isinstance(key, str):
            continue
        enabled = bool(overrides.get(key)) if key in overrides else bool(d.get("enabled"))
        items.append({"key": key, "enabled": enabled})
    resp = make_response(jsonify({"items": items}), 200)
    return _no_store(resp)


@bp.post("/feature-flags/<string:key>:toggle")
@require_roles("superuser")
def feature_flags_toggle(key: str):
    """Toggle a feature flag for the current tenant by setting a tenant-scoped override.

    Effective = override if present else registry default.
    This flips the effective state by writing an override (enable/disable).
    """
    tid = session.get("tenant_id")
    if not tid:
        return jsonify({"title": "Validation error", "detail": "Tenant context saknas"}), 400
    # Determine current effective state
    # Registry default
    try:
        registry = current_app.feature_registry
        default_on = bool(registry.enabled(key))
    except Exception:
        default_on = False
    # Tenant override
    db = get_session()
    cur_on = default_on
    try:
        row = db.query(TenantFeatureFlag).filter(
            TenantFeatureFlag.tenant_id == int(tid), TenantFeatureFlag.name == key
        ).first()
        if row is not None:
            cur_on = bool(row.enabled)
    finally:
        db.close()
    new_state = not cur_on
    # Apply via FeatureService if available, else write directly
    try:
        svc = current_app.feature_service
        if new_state:
            svc.enable(int(tid), key)
        else:
            svc.disable(int(tid), key)
    except Exception:
        # Fallback direct upsert
        db = get_session()
        try:
            row = db.query(TenantFeatureFlag).filter(
                TenantFeatureFlag.tenant_id == int(tid), TenantFeatureFlag.name == key
            ).first()
            if row is None:
                row = TenantFeatureFlag(tenant_id=int(tid), name=key, enabled=new_state)
                db.add(row)
            else:
                row.enabled = new_state
            db.commit()
        finally:
            db.close()
    # Audit (best effort)
    try:
        from .audit_events import record_audit_event

        record_audit_event(
            "FLAG_TOGGLED",
            actor_user_id=session.get("user_id"),
            tenant_id=int(tid),
            flag=key,
            enabled=new_state,
        )
    except Exception:
        pass
    resp = make_response(jsonify({"key": key, "enabled": new_state}), 200)
    return _no_store(resp)
