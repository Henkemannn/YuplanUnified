from __future__ import annotations

from flask import Response, current_app


def set_secure_cookie(
    resp: Response,
    name: str,
    value: str,
    *,
    httponly: bool = True,
    samesite: str = "Lax",
    max_age: int | None = None,
    path: str = "/",
) -> None:
    """Set a cookie with security-oriented defaults.

    Secure flag is enabled unless DEBUG/TESTING; this keeps local dev convenient.
    """
    secure_flag = not (current_app.config.get("DEBUG") or current_app.config.get("TESTING"))
    resp.set_cookie(
        name,
        value,
        secure=secure_flag,
        httponly=httponly,
        samesite=samesite,
        max_age=max_age,
        path=path,
    )

__all__ = ["set_secure_cookie"]