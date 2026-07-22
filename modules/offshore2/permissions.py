from __future__ import annotations

from flask import current_app, g, request
from sqlalchemy import text

from core.db import get_session
from core.models import TenantFeatureFlag
from core.http_errors import not_found

FEATURE_FLAG = "offshore.v2.enabled"
VIEWER_ROLES = ("admin", "superuser", "cook", "editor", "viewer")
MANAGER_ROLES = ("admin", "superuser")
PREP_WRITE_ROLES = ("cook", "editor", "admin", "superuser")


def feature_enabled() -> bool:
    override = getattr(g, "tenant_feature_flags", None)
    if isinstance(override, dict) and FEATURE_FLAG in override:
        return bool(override.get(FEATURE_FLAG))
    helper = getattr(current_app, "feature_enabled", None)
    if callable(helper):
        enabled = bool(helper(FEATURE_FLAG))
        if enabled:
            return True
    registry = getattr(current_app, "feature_registry", None)
    if registry and registry.enabled(FEATURE_FLAG):
        return True

    # Defensive fallback: resolve the current request's site/tenant overrides directly.
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is None:
        tenant_id_raw = request.headers.get("X-Tenant-Id")
        if isinstance(tenant_id_raw, str) and tenant_id_raw.isdigit():
            tenant_id = int(tenant_id_raw)
    site_id = (
        request.args.get("site_id")
        or request.cookies.get("site_id")
        or request.headers.get("X-Site-Id")
        or getattr(g, "site_id", None)
        or request.cookies.get("session_site_id")
        or ""
    ).strip()

    db = get_session()
    try:
        if site_id:
            try:
                rows = db.execute(
                    text("SELECT name, enabled FROM site_feature_flags WHERE site_id=:sid"),
                    {"sid": site_id},
                ).fetchall()
                for row in rows:
                    if str(row[0]) == FEATURE_FLAG:
                        return bool(int(row[1]))
            except Exception:
                pass
        if tenant_id is not None:
            rows = (
                db.query(TenantFeatureFlag.name, TenantFeatureFlag.enabled)
                .filter(TenantFeatureFlag.tenant_id == int(tenant_id))
                .all()
            )
            for name, enabled in rows:
                if str(name) == FEATURE_FLAG:
                    return bool(enabled)
    finally:
        db.close()
    return False


def gate_or_404():
    if not feature_enabled():
        return not_found("Offshore module is not enabled")
    return None


def active_site_context() -> tuple[int | None, str | None]:
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is None:
        tenant_id_raw = request.headers.get("X-Tenant-Id")
        if isinstance(tenant_id_raw, str) and tenant_id_raw.isdigit():
            tenant_id = int(tenant_id_raw)
    site_id = (request.args.get("site_id") or "").strip() or None
    return tenant_id, site_id


def can_manage(role: str | None) -> bool:
    return (role or "").strip().lower() in MANAGER_ROLES


def can_write_prep(role: str | None) -> bool:
    return (role or "").strip().lower() in PREP_WRITE_ROLES
