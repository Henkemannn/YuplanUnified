from __future__ import annotations

import os
import time
from collections.abc import Callable
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_session
from .jwt_utils import (
    DEFAULT_ACCESS_TTL,
    DEFAULT_REFRESH_TTL,
    JWTError,
    decode as jwt_decode,
    issue_token_pair,
)
from .models import Tenant, User

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
            auth_header = request.headers.get("Authorization","")
            secret = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET","dev-secret"))
            # Always prefer bearer header if present (stateless override of session)
            if auth_header.lower().startswith("bearer "):
                token = auth_header.split(None,1)[1].strip()
                try:
                    payload = jwt_decode(token, secret=secret)
                    session["user_id"] = payload.get("sub")
                    session["role"] = payload.get("role")
                    session["tenant_id"] = payload.get("tenant_id")
                except JWTError:
                    return _json_error("auth required", 401)
            if not session.get("user_id"):
                return _json_error("auth required", 401)
            user_role = session.get("role")
            if roles and user_role not in roles:
                # Provide which role(s) required in message
                return jsonify({"error":"forbidden","message": f"required role in {roles}"}), 403
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
    rl_cfg = current_app.config.get("AUTH_RATE_LIMIT", {"window_sec": 300, "max_failures": 5, "lock_sec": 600})
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
            return _json_error("rate_limited", 429)
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
                return _json_error("rate_limited", 429)
            return _json_error("invalid credentials", 401)
        secret = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET","dev-secret"))
        access, refresh, refresh_jti = issue_token_pair(user_id=user.id, role=user.role, tenant_id=user.tenant_id, secret=secret,
                                                        access_ttl=current_app.config.get("JWT_ACCESS_TTL", DEFAULT_ACCESS_TTL),
                                                        refresh_ttl=current_app.config.get("JWT_REFRESH_TTL", DEFAULT_REFRESH_TTL))
        user.refresh_token_jti = refresh_jti
        db.commit()
        if key in store:
            del store[key]
        return jsonify({
            "ok": True,
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": DEFAULT_ACCESS_TTL,
        })
    finally:
        db.close()

@bp.post("/logout")
def logout():
    # Accept refresh token or Authorization header, invalidate stored jti
    secret = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET","dev-secret"))
    token = None
    auth = request.headers.get("Authorization","")
    if auth.lower().startswith("bearer "):
        token = auth.split(None,1)[1].strip()
    body = request.get_json(silent=True) or {}
    token = token or body.get("refresh_token") or body.get("token")
    if not token:
        return _json_error("missing token", 400)
    try:
        payload = jwt_decode(token, secret=secret)
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
    secret = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET","dev-secret"))
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token")
    if not token:
        return _json_error("missing token", 400)
    try:
        payload = jwt_decode(token, secret=secret)
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
        access, new_refresh, new_jti = issue_token_pair(user_id=user.id, role=user.role, tenant_id=user.tenant_id, secret=secret,
                                                        access_ttl=current_app.config.get("JWT_ACCESS_TTL", DEFAULT_ACCESS_TTL),
                                                        refresh_ttl=current_app.config.get("JWT_REFRESH_TTL", DEFAULT_REFRESH_TTL))
        user.refresh_token_jti = new_jti
        db.commit()
        return jsonify({"ok": True, "access_token": access, "refresh_token": new_refresh, "token_type": "Bearer", "expires_in": DEFAULT_ACCESS_TTL})
    finally:
        db.close()

@bp.get("/me")
def me():
    # Prefer bearer token if supplied (stateless); fallback to session.
    secret = current_app.config.get("JWT_SECRET", os.getenv("JWT_SECRET","dev-secret"))
    auth = request.headers.get("Authorization","")
    user_id = None
    role = None
    tenant_id = None
    if auth.lower().startswith("bearer "):
        token = auth.split(None,1)[1].strip()
        try:
            payload = jwt_decode(token, secret=secret)
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
    return jsonify({
        "ok": True,
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })

# --- Bootstrap Superuser Utility ---
def ensure_bootstrap_superuser():
    email = os.getenv("SUPERUSER_EMAIL")
    password = os.getenv("SUPERUSER_PASSWORD")
    if not email or not password:
        return
    db = get_session()
    try:
        has_user = db.query(User).first()
        if has_user:
            return
        # Create tenant
        tenant = Tenant(name="Primary")
        db.add(tenant)
        db.flush()
        pw_hash = generate_password_hash(password)
        user = User(tenant_id=tenant.id, email=email.lower(), password_hash=pw_hash, role="superuser", unit_id=None)
        db.add(user)
        db.commit()
        current_app.logger.info("Bootstrap superuser created: %s", email)
    finally:
        db.close()
