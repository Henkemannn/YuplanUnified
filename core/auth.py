from __future__ import annotations

import os
import time
from collections.abc import Callable
from functools import wraps

from flask import Blueprint, current_app, jsonify, make_response, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_session
from .jwt_utils import (
    DEFAULT_ACCESS_TTL,
    DEFAULT_REFRESH_TTL,
    JWTError,
    decode as jwt_decode,
    issue_token_pair,
    select_signing_secret,
)
from .models import Tenant, User

# Legacy error envelopes are used for auth endpoints to preserve compatibility with tests/clients.

bp = Blueprint("auth", __name__, url_prefix="/auth")

# In-memory rate limit store: key -> {failures:int, first:ts, lock_until:ts?}
_RATE_LIMIT_STORE: dict[str, dict[str, float | int]] = {}

# --- Helpers ---


def _json_error(msg: str, code: int = 400):
    return jsonify({"error": msg, "message": msg}), code


def require_roles(*roles: str):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            primary = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
            secrets_list = current_app.config.get("JWT_SECRETS") or []
            # Always prefer bearer header if present (stateless override of session)
            if auth_header.lower().startswith("bearer "):
                token = auth_header.split(None, 1)[1].strip()
                cfg = current_app.config
                try:
                    payload = jwt_decode(
                        token,
                        secret=primary,
                        secrets_list=secrets_list,
                        issuer=cfg.get("JWT_ISSUER"),
                        audience=cfg.get("JWT_AUDIENCE"),
                        leeway=cfg.get("JWT_LEEWAY_SECONDS", 60),
                        max_age=cfg.get("JWT_MAX_AGE_SECONDS"),
                    )
                    session["user_id"] = payload.get("sub")
                    session["role"] = payload.get("role")
                    session["tenant_id"] = payload.get("tenant_id")
                except JWTError as e:
                    if current_app.config.get("TESTING"):
                        current_app.logger.debug({"jwt_reject": str(e)})
                    return _json_error("auth required", 401)
            if not session.get("user_id"):
                return _json_error("auth required", 401)
            user_role = session.get("role")
            if roles and user_role not in roles:
                # Debug aid for test harness: log mismatch context when TESTING to diagnose unexpected 403s
                if current_app.config.get("TESTING"):
                    try:
                        current_app.logger.info(
                            {
                                "auth_debug": True,
                                "where": "require_roles",
                                "expected_any_of": roles,
                                "session_role": user_role,
                                "session_keys": list(session.keys()),
                            }
                        )
                    except Exception:
                        pass
                # Provide which role(s) required in message with ok False envelope
                return jsonify(
                    {"ok": False, "error": "forbidden", "message": f"required role in {roles}"}
                ), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --- Routes ---
@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return _json_error("missing credentials", 400)
    # Rate limiting (simple in-memory). Key by email + remote addr.
    rl_cfg = current_app.config.get(
        "AUTH_RATE_LIMIT", {"window_sec": 300, "max_failures": 5, "lock_sec": 600}
    )
    window_sec = rl_cfg.get("window_sec", 300)
    max_failures = rl_cfg.get("max_failures", 5)
    lock_sec = rl_cfg.get("lock_sec", 600)
    now = time.time()
    ip = request.remote_addr or "na"
    key = f"{email}:{ip}"
    store = _RATE_LIMIT_STORE
    rec = store.get(key)
    if rec:
        # rec = {failures: int, first: ts, lock_until: ts?}
        lock_until = rec.get("lock_until")
        if lock_until and lock_until > now:
            resp = make_response(jsonify({"error": "rate_limited", "message": "rate_limited"}), 429)
            resp.headers["Retry-After"] = str(int(lock_until - now))
            return resp
        # slide window
        if now - rec["first"] > window_sec:
            rec["first"] = now
            rec["failures"] = 0
    else:
        rec = {"failures": 0, "first": now}
        store[key] = rec
    db = get_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            rec["failures"] += 1
            if rec["failures"] >= max_failures:
                rec["lock_until"] = now + lock_sec
                resp = make_response(
                    jsonify({"error": "rate_limited", "message": "rate_limited"}), 429
                )
                resp.headers["Retry-After"] = str(lock_sec)
                return resp
            return _json_error("invalid credentials", 401)
        secrets_list = current_app.config.get("JWT_SECRETS") or []
        primary = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
        signing_secret = select_signing_secret(primary, secrets_list)
        access, refresh, refresh_jti = issue_token_pair(
            user_id=user.id,
            role=user.role,
            tenant_id=user.tenant_id,
            secret=signing_secret,
            access_ttl=current_app.config.get("JWT_ACCESS_TTL", DEFAULT_ACCESS_TTL),
            refresh_ttl=current_app.config.get("JWT_REFRESH_TTL", DEFAULT_REFRESH_TTL),
            audience=current_app.config.get("JWT_AUDIENCE", "api"),
        )
        user.refresh_token_jti = refresh_jti
        db.commit()
        if key in store:
            del store[key]
        # Persist session for tests that rely on cookie-based auth instead of bearer header
        session["user_id"] = user.id
        session["role"] = user.role
        session["tenant_id"] = user.tenant_id
        # CSRF token issuance (double submit). Provide if not present already.
        csrf_cookie_name = current_app.config.get("CSRF_COOKIE_NAME", "csrf_token")
        csrf_token = request.cookies.get(csrf_cookie_name)
        if not csrf_token:
            import secrets

            csrf_token = secrets.token_hex(16)
        resp = make_response(
            jsonify(
                {
                    "ok": True,
                    "access_token": access,
                    "refresh_token": refresh,
                    "token_type": "Bearer",
                    "expires_in": DEFAULT_ACCESS_TTL,
                    "csrf_token": csrf_token,
                }
            )
        )
        from .cookies import set_secure_cookie

        set_secure_cookie(resp, csrf_cookie_name, csrf_token, httponly=False, samesite="Strict")
        return resp
    finally:
        db.close()


@bp.post("/logout")
def logout():
    # Accept refresh token or Authorization header, invalidate stored jti
    primary = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
    secrets_list = current_app.config.get("JWT_SECRETS") or []
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1].strip()
    body = request.get_json(silent=True) or {}
    token = token or body.get("refresh_token") or body.get("token")
    if not token:
        return _json_error("missing token", 400)
    try:
        payload = jwt_decode(token, secret=primary, secrets_list=secrets_list)
    except JWTError:
        return _json_error("invalid token", 401)
    if payload.get("type") != "refresh":
        return _json_error("wrong token type", 400)
    db = get_session()
    try:
        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if user and user.refresh_token_jti == payload.get("jti"):
            user.refresh_token_jti = None
            db.commit()
    finally:
        db.close()
    return jsonify({"ok": True})


@bp.post("/refresh")
def refresh():
    primary = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
    secrets_list = current_app.config.get("JWT_SECRETS") or []
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token")
    if not token:
        return _json_error("missing token", 400)
    try:
        payload = jwt_decode(token, secret=primary, secrets_list=secrets_list)
    except JWTError:
        return _json_error("invalid token", 401)
    if payload.get("type") != "refresh":
        return _json_error("wrong token type", 400)
    db = get_session()
    try:
        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if not user:
            return _json_error("invalid token", 401)
        if user.refresh_token_jti != payload.get("jti"):
            return _json_error("invalid token", 401)
        # rotate
        signing_secret = select_signing_secret(primary, secrets_list)
        access, new_refresh, new_jti = issue_token_pair(
            user_id=user.id,
            role=user.role,
            tenant_id=user.tenant_id,
            secret=signing_secret,
            access_ttl=current_app.config.get("JWT_ACCESS_TTL", DEFAULT_ACCESS_TTL),
            refresh_ttl=current_app.config.get("JWT_REFRESH_TTL", DEFAULT_REFRESH_TTL),
        )
        user.refresh_token_jti = new_jti
        db.commit()
        return jsonify(
            {
                "ok": True,
                "access_token": access,
                "refresh_token": new_refresh,
                "token_type": "Bearer",
                "expires_in": DEFAULT_ACCESS_TTL,
            }
        )
    finally:
        db.close()


@bp.get("/me")
def me():
    # Prefer bearer token if supplied (stateless); fallback to session.
    primary = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
    secrets_list = current_app.config.get("JWT_SECRETS") or []
    auth = request.headers.get("Authorization", "")
    user_id = None
    role = None
    tenant_id = None
    if auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1].strip()
        try:
            payload = jwt_decode(token, secret=primary, secrets_list=secrets_list)
            user_id = payload.get("sub")
            role = payload.get("role")
            tenant_id = payload.get("tenant_id")
        except JWTError:
            return _json_error("auth required", 401)
    else:
        user_id = session.get("user_id")
        role = session.get("role")
        tenant_id = session.get("tenant_id")
    if not user_id:
        return _json_error("auth required", 401)
    return jsonify(
        {
            "ok": True,
            "user_id": user_id,
            "role": role,
            "tenant_id": tenant_id,
        }
    )


# --- Bootstrap Superuser Utility ---
def ensure_bootstrap_superuser():
    """Create a bootstrap superuser in development when env vars are provided.

    Behavior:
    - Requires SUPERUSER_EMAIL and SUPERUSER_PASSWORD.
    - If tables are missing and DEV_CREATE_ALL/YUPLAN_DEV_CREATE_ALL is set to 1, auto-create schema.
    - If DB isn't ready or tables are missing and auto-create isn't enabled, skip silently.
    This avoids crashing app startup on a fresh environment.
    """
    email = os.getenv("SUPERUSER_EMAIL")
    password = os.getenv("SUPERUSER_PASSWORD")
    if not email or not password:
        return

    auto_create = (
        os.getenv("DEV_CREATE_ALL", "0") == "1" or os.getenv("YUPLAN_DEV_CREATE_ALL", "0") == "1"
    )

    try:
        db = get_session()
    except Exception:
        # DB session factory not initialized yet
        return

    try:
        # Ensure schema exists when allowed in dev
        if auto_create:
            try:
                from .db import create_all as _create_all  # local import to avoid cycles

                _create_all()
            except Exception:
                # Non-fatal; continue and let the next step decide
                pass

        # Check that required tables exist; if not, skip (or they were just created)
        try:
            from sqlalchemy import inspect as _sa_inspect  # type: ignore

            inspector = _sa_inspect(db.bind)
            has_users = inspector.has_table("users")
            has_tenants = inspector.has_table("tenants")
            if not (has_users and has_tenants):
                return
        except Exception:
            # If inspection fails (e.g., driver-specific), best effort: try a safe query and catch
            pass

        # Proceed only if there are no users
        try:
            has_user = db.query(User).first()
        except Exception:
            # Likely missing tables; nothing to do
            return
        if has_user:
            return

        # Create tenant and superuser
        tenant = Tenant(name="Primary")
        db.add(tenant)
        db.flush()
        pw_hash = generate_password_hash(password)
        user = User(
            tenant_id=tenant.id,
            email=email.lower(),
            password_hash=pw_hash,
            role="superuser",
            unit_id=None,
        )
        db.add(user)
        db.commit()
        try:
            current_app.logger.info("Bootstrap superuser created: %s", email)
        except Exception:
            pass
    finally:
        db.close()
