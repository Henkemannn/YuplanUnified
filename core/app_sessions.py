"""Pocket 6 - Session management helpers.

Copilot prompt: Refactor require_session to raise SessionError(401) instead of returning a Response. Keep SessionData TypedDict. No Any.
"""
from __future__ import annotations

from typing import Literal, TypedDict, cast

from flask import session as flask_session

Role = Literal["superuser","admin","editor","viewer"]

class SessionData(TypedDict):
    user_id: int
    role: str
    tenant_id: int


def persist_login(sess, user_id: int, role: str, tenant_id: int) -> None:
    """Persist minimal auth session state. (Thin wrapper to allow future swap)."""
    sess["user_id"] = int(user_id)
    sess["role"] = role
    sess["tenant_id"] = int(tenant_id)


def get_session(sess=flask_session) -> SessionData | None:
    if not sess.get("user_id") or not sess.get("tenant_id") or not sess.get("role"):
        return None
    data: SessionData = {
        "user_id": int(sess["user_id"]),
        "role": cast(str, sess["role"]),
        "tenant_id": int(sess["tenant_id"]),
    }
    return data


def require_session(sess=flask_session) -> SessionData:
    data = get_session(sess)
    if data is None:
        raise SessionError("authentication required")
    return data


class SessionError(Exception):
    """Signals a 401 unauthorized due to missing/invalid session."""
    def __init__(self, message: str = "authentication required"):
        super().__init__(message)

__all__ = [
    "Role",
    "SessionData",
    "persist_login",
    "get_session",
    "require_session",
    "SessionError",
]
