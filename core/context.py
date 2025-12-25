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
