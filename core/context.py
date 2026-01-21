from __future__ import annotations

from typing import TypedDict, Optional

from flask import g, session


class ActiveContext(TypedDict):
    tenant_id: Optional[int]
    site_id: Optional[str]


def get_active_context() -> ActiveContext:
    """Return canonical active context: tenant_id from auth/impersonation, site_id from session.

    No guessing: if site_id is missing, callers should redirect to a site selector.
    """
    tid = getattr(g, "tenant_id", None)
    try:
        # session may carry tenant_id as well; prefer g when set
        if tid is None:
            val = session.get("tenant_id")
            if isinstance(val, int):
                tid = val
            elif isinstance(val, str) and val.isdigit():
                tid = int(val)
    except Exception:
        pass
    sid = None
    try:
        val = session.get("site_id")
        if isinstance(val, str):
            sid = val.strip() or None
    except Exception:
        sid = None
    return {"tenant_id": tid, "site_id": sid}


__all__ = ["get_active_context", "ActiveContext"]


def get_single_site_id_for_tenant(tenant_id: int | str) -> str | None:
    """Return the only site_id for a tenant if exactly one exists; else None.

    Uses SitesRepo to respect existing data access and SQLite-safe behavior.
    """
    try:
        from .admin_repo import SitesRepo
        sites = SitesRepo().list_sites_for_tenant(tenant_id)
        if isinstance(sites, list) and len(sites) == 1:
            one = sites[0]
            # SitesRepo returns dicts {id,name,version}
            sid = (one.get("id") if isinstance(one, dict) else None)
            return str(sid) if sid else None
    except Exception:
        return None
    return None
