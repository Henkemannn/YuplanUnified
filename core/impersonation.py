"""Superuser impersonation (skeleton).

Provides helpers to start/stop an impersonation session. When active, the
effective tenant context for the request becomes the impersonated tenant and
RBAC can treat the superuser as an admin for operational endpoints. A later
iteration can enforce time limits + audit persistence.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from flask import current_app, g, session

from .audit_events import record_audit_event

SESSION_KEY = "impersonate"


@dataclass
class ImpersonationState:
    tenant_id: int
    reason: str
    started_at: int
    expires_at: int
    admin_user_id: int | None = None
    admin_roles: list[str] | None = None

    def age(self) -> int:
        return int(time.time() - self.started_at)

    def remaining(self) -> int:
        return max(0, self.expires_at - int(time.time()))


def _max_age() -> int:
    try:
        return int(current_app.config.get("IMPERSONATION_MAX_AGE_SECONDS") or 900)
    except Exception:
        return 900


def start_impersonation(tenant_id: int, reason: str) -> None:
    now = int(time.time())
    roles = session.get("roles") or ([] if not session.get("role") else [session.get("role")])
    state = {
        "tenant_id": int(tenant_id),
        "reason": reason or "",
        "started_at": now,
        "expires_at": now + _max_age(),
        "admin_user_id": session.get("user_id"),
        "admin_roles": roles,
    }
    session[SESSION_KEY] = state
    record_audit_event(
        "impersonation_start",
        actor_user_id=session.get("user_id"),
        tenant_id=int(tenant_id),
        reason=reason,
        expires_at=state["expires_at"],
    )


def stop_impersonation() -> None:
    st = session.pop(SESSION_KEY, None)
    if st:
        record_audit_event(
            "impersonation_stop",
            actor_user_id=session.get("user_id"),
            tenant_id=st.get("tenant_id") if isinstance(st, dict) else None,
        )


def get_impersonation(raw: bool = False) -> ImpersonationState | None:
    data: dict[str, Any] | None = session.get(SESSION_KEY)  # type: ignore[assignment]
    if not data:
        return None
    try:
        st = ImpersonationState(
            tenant_id=int(data["tenant_id"]),
            reason=str(data.get("reason") or ""),
            started_at=int(data.get("started_at") or 0),
            expires_at=int(data.get("expires_at") or 0),
            admin_user_id=(int(data.get("admin_user_id")) if data.get("admin_user_id") else None),
            admin_roles=list(data.get("admin_roles") or []),
        )
    except Exception:
        return None
    if raw:
        return st
    # Expiry enforcement
    if st.expires_at and time.time() > st.expires_at:
        # Auto-stop on expiry (separate audit event)
        session.pop(SESSION_KEY, None)
        record_audit_event(
            "impersonation_auto_expire",
            actor_user_id=session.get("user_id"),
            tenant_id=st.tenant_id,
            started_at=st.started_at,
        )
        g.impersonation_expired = True
        return None
    return st


def apply_impersonation() -> None:
    st = get_impersonation()
    if not st:
        return
    g.impersonating = True
    g.impersonation_remaining = st.remaining()
    g.impersonation_reason = st.reason
    # Override tenant context
    g.tenant_id = st.tenant_id
    # Promote role logically to admin for the duration of request if not present
    roles = session.get("roles") or []
    if "admin" not in roles:
        roles.append("admin")
        session["roles"] = roles
