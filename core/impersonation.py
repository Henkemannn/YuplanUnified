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
    if session.get("role") != "superuser":
        raise PermissionError("superuser_required")
    now = int(time.time())
    roles = list(session.get("roles") or [])
    if not roles and session.get("role"):
        roles = [session.get("role")]
    previous = get_impersonation(raw=True)
    if previous and previous.admin_roles is not None and "admin" not in previous.admin_roles:
        roles = [role for role in roles if role != "admin"]
        if not roles and session.get("role"):
            roles = [session.get("role")]
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


def _restore_roles(st: ImpersonationState | None, *, owner_matches: bool) -> None:
    if owner_matches and st is not None and st.admin_roles is not None:
        session["roles"] = list(st.admin_roles)
        return
    role = str(session.get("role") or "").strip()
    roles = list(session.get("roles") or [])
    if role:
        session["roles"] = [role]
    else:
        session.pop("roles", None)


def _clear_impersonation_state(st: ImpersonationState | None) -> None:
    owner_matches = bool(
        st is not None
        and st.admin_user_id is not None
        and int(st.admin_user_id) == int(session.get("user_id") or 0)
    )
    session.pop(SESSION_KEY, None)
    session.pop("site_id", None)
    _restore_roles(st, owner_matches=owner_matches)
    authenticated_tenant_id = session.get("authenticated_tenant_id")
    if authenticated_tenant_id is not None:
        session["tenant_id"] = authenticated_tenant_id
        g.tenant_id = authenticated_tenant_id
    g.site_id = None
    g.impersonating = False


def stop_impersonation() -> None:
    st = session.pop(SESSION_KEY, None)
    if st:
        record_audit_event(
            "impersonation_stop",
            actor_user_id=session.get("user_id"),
            tenant_id=st.get("tenant_id") if isinstance(st, dict) else None,
        )
    parsed_state = None
    if isinstance(st, dict):
        try:
            parsed_state = ImpersonationState(
                tenant_id=int(st["tenant_id"]),
                reason=str(st.get("reason") or ""),
                started_at=int(st.get("started_at") or 0),
                expires_at=int(st.get("expires_at") or 0),
                admin_user_id=(int(st.get("admin_user_id")) if st.get("admin_user_id") else None),
                admin_roles=list(st.get("admin_roles") or []),
            )
        except (KeyError, TypeError, ValueError):
            pass
    _clear_impersonation_state(parsed_state)


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
        _clear_impersonation_state(st)
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
    raw_state = session.get(SESSION_KEY)
    st = get_impersonation()
    if not st:
        if raw_state:
            g.impersonation_invalid = True
        return
    if (
        session.get("role") != "superuser"
        or st.admin_user_id is None
        or int(st.admin_user_id) != int(session.get("user_id") or 0)
    ):
        _clear_impersonation_state(st)
        g.impersonation_invalid = True
        return
    g.impersonating = True
    g.impersonation_remaining = st.remaining()
    g.impersonation_reason = st.reason
    # Override tenant context
    g.tenant_id = st.tenant_id
    # Ensure session also carries tenant context for code reading from session
    try:
        session[SESSION_KEY] = session.get(SESSION_KEY)  # preserve existing state
        session["tenant_id"] = st.tenant_id
        g.site_id = session.get("site_id")
    except Exception:
        pass
    # Promote role logically to admin for the duration of request if not present
    roles = session.get("roles") or []
    if "admin" not in roles:
        roles.append("admin")
        session["roles"] = roles


def synchronize_authenticated_context(
    *,
    user_id: int,
    role: str,
    tenant_id: int,
) -> int:
    """Keep authenticated identity separate from the effective support tenant."""
    g.user_id = int(user_id)
    session["authenticated_user_id"] = int(user_id)
    session["authenticated_role"] = str(role)
    session["authenticated_tenant_id"] = int(tenant_id)

    if getattr(g, "impersonation_expired", False):
        session.pop(SESSION_KEY, None)
        session.pop("site_id", None)
        session["tenant_id"] = int(tenant_id)
        g.tenant_id = int(tenant_id)
        g.site_id = None
        g.impersonating = False
        return int(tenant_id)

    if getattr(g, "impersonation_invalid", False):
        raise PermissionError("invalid_impersonation_context")

    raw_state = session.get(SESSION_KEY)
    st = get_impersonation()
    if not st:
        if raw_state:
            raise PermissionError("invalid_impersonation_context")
        session["tenant_id"] = int(tenant_id)
        g.tenant_id = int(tenant_id)
        return int(tenant_id)

    if str(role).strip().lower() != "superuser" or st.admin_user_id != int(user_id):
        _clear_impersonation_state(st)
        raise PermissionError("invalid_impersonation_owner")

    effective_tenant_id = int(st.tenant_id)
    selected_site_id = str(session.get("site_id") or "").strip() or None
    if selected_site_id:
        from .db import get_site_tenant

        site_tenant_id = get_site_tenant(selected_site_id)
        if site_tenant_id is None or int(site_tenant_id) != effective_tenant_id:
            raise PermissionError("invalid_impersonation_site")

    session["tenant_id"] = effective_tenant_id
    g.tenant_id = effective_tenant_id
    g.site_id = selected_site_id
    g.impersonating = True
    return effective_tenant_id
