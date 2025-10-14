from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, make_response, request, current_app
from sqlalchemy import func, select, text

from .auth import require_roles
from .db import get_session
from .models import AuditEvent, Tenant, TenantFeatureFlag

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
    payload = row.payload if isinstance(getattr(row, 'payload', None), dict) else {}
    name = payload.get('name') or payload.get('tenant') or payload.get('tenant_name')
    flag = payload.get('flag') or payload.get('feature')
    module = payload.get('module') or payload.get('module_name')
    # Heuristics per spec
    if kind == 'TENANT_CREATED' and name:
        return f"Tenant skapad – {name} skapad"
    if kind == 'TENANT_UPDATED' and name:
        return f"Tenant uppdaterad – {name} uppdaterad"
    if kind == 'FLAG_TOGGLED' and flag is not None:
        state = payload.get('enabled') or payload.get('on') or payload.get('state')
        onoff = 'på' if str(state).lower() in ('1', 'true', 'yes', 'on') else 'av'
        return f"Flagga ändrad – {flag} {onoff}"
    if kind == 'MODULE_INSTALLED' and module:
        return f"Modul installerad – {module} installerad"
    if kind == 'MODULE_ENABLED' and module:
        return f"Modul aktiverad – {module} aktiverad"
    # fallback
    return f"Händelse – {kind}" if kind else "Händelse"


def _event_badge(kind: str, row: AuditEvent) -> str:
    if kind.startswith('TENANT_'):
        return 'TENANT'
    if kind.startswith('MODULE_'):
        return 'MODUL'
    p = row.payload if isinstance(getattr(row, 'payload', None), dict) else {}
    # If flag in kind or payload name
    if 'FLAG' in kind or 'flag' in p or 'feature' in p:
        return 'FLAG'
    return 'INFO'


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


__all__ = ["bp"]
