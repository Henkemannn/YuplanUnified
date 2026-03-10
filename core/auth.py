from __future__ import annotations

import os
import time
from collections.abc import Callable
from functools import wraps

from flask import Blueprint, current_app, jsonify, make_response, request, session, render_template
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

# TODO[P7A-auth-inventory]: Contracts extracted from tests
# - Endpoints: POST `/auth/login`, POST `/auth/refresh`, GET `/auth/me`.
# - Login JSON: `{ok: true, access_token, refresh_token, token_type: "Bearer", expires_in, csrf_token}`.
# - Refresh JSON: rotates refresh; reusing old refresh_token yields 401 `invalid token`.
# - CSRF cookie: name `csrf_token`, `SameSite=Strict`, `HttpOnly=false`, `Secure` depends on `TESTING` (off in tests).
# - Rate limit: failed login attempts return 429 with `Retry-After` header and `{error:"rate_limited"}` envelope.
# - Unauthorized/Forbidden: use legacy `{ok:false|missing, error|message}` style; 401 `auth required`, 403 includes required role in message.
# - RBAC adapter: map roles via `roles.to_canonical`; `cook->viewer`, `unit_portal->editor`.
# - Bearer header should override session when present on protected routes.


def _json_error(msg: str, code: int = 400):
    # Standardize unauthorized detail expected by tests
    normalized = msg
    if code == 401 and msg == "auth required":
        normalized = "authentication required"
    return jsonify({"error": normalized, "message": normalized}), code


def _jwt_primary_secret() -> str | None:
    secret = (current_app.config.get("JWT_SECRET") or os.getenv("JWT_SECRET") or "").strip()
    return secret or None


def set_csrf_cookie(resp, token: str):
    """Set CSRF cookie with flags differing for test/dev vs prod.

    Tests expect SameSite=Strict, HttpOnly=false; Secure off in testing.
    We reuse `set_secure_cookie` to handle Secure based on DEBUG/TESTING,
    and explicitly set httponly=False, samesite="Strict".
    """
    from .cookies import set_secure_cookie

    # In DEBUG/TESTING use Lax to reduce local cross-site blocking; Strict in other modes
    samesite_val = "Strict"
    try:
        import os as _os
        if not current_app.config.get("TESTING") and _os.getenv("DEV_CSRF_LAX", "0") in ("1", "true", "yes"):
            samesite_val = "Lax"
    except Exception:
        pass
    set_secure_cookie(
        resp,
        current_app.config.get("CSRF_COOKIE_NAME", "csrf_token"),
        token,
        httponly=False,
        samesite=samesite_val,
    )


def require_roles(*roles: str):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            primary = _jwt_primary_secret()
            secrets_list = current_app.config.get("JWT_SECRETS") or []
            # Always prefer bearer header if present (stateless override of session)
            if auth_header.lower().startswith("bearer "):
                if not primary:
                    return _json_error("auth required", 401)
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
                    session["role"] = _normalize_role(payload.get("role"))
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


def _normalize_role(role: str | None) -> str:
    r = (role or "").strip().lower()
    if r == "tenant_admin":
        return "admin"
    if r == "system_admin":
        return "superuser"
    return r


def _emit_dev_auth_fingerprint(tag: str) -> None:
    try:
        logger = current_app.config.get("DEV_AUTH_FINGERPRINT_LOGGER")
        if callable(logger):
            logger(tag)
    except Exception:
        pass


# --- Routes ---
@bp.post("/login")
def login():
    # Staging simple auth shortcut (env flag) bypasses normal credential path.
    # Disabled during TESTING to avoid interfering with auth tests.
    if (
        os.getenv("STAGING_SIMPLE_AUTH", "0") in ("1", "true", "yes")
        and current_app.config.get("DEMO_AUTH_ENABLED") is True
        and not current_app.config.get("TESTING")
    ):
        data = request.get_json(silent=True) or {}
        role = (data.get("role") or "admin").strip().lower()
        if role not in ("admin", "staff"):
            role = "staff"
        session["user_id"] = 99999  # demo user id placeholder
        session["role"] = role
        session["tenant_id"] = 51  # arbitrary demo tenant
        resp = make_response(jsonify({"ok": True, "demo": True, "role": role}))
        # Lightweight signed-ish cookie (not cryptographically strong; staging only)
        resp.set_cookie("yp_demo", role, httponly=True, samesite="Lax")
        _emit_dev_auth_fingerprint("login_ok")
        return resp
    data = request.get_json(silent=True) or {}
    # Fallback to form fields when JSON isn't provided (browser form posts)
    if not data:
        data = {"email": request.form.get("email"), "password": request.form.get("password")}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    # Always issue a CSRF cookie for clients (tests assert cookie presence even on errors)
    csrf_cookie_name = current_app.config.get("CSRF_COOKIE_NAME", "csrf_token")
    csrf_token = request.cookies.get(csrf_cookie_name)
    if not csrf_token:
        import secrets

        csrf_token = secrets.token_hex(16)
    if not email or not password:
        resp = make_response(jsonify({"error": "missing credentials", "message": "missing credentials"}), 400)
        set_csrf_cookie(resp, csrf_token)
        return resp
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
        # Login user lookup: filter by exact match on email with lowercased input from above.
        # No tenant/site filters; no is_active enforced.
        user = db.query(User).filter(User.email == email).first()
        user_found = bool(user)
        password_ok = bool(user and check_password_hash(user.password_hash, password))
        if (not user_found) or (not password_ok):
            rec["failures"] += 1
            if rec["failures"] >= max_failures:
                rec["lock_until"] = now + lock_sec
                resp = make_response(
                    jsonify({"error": "rate_limited", "message": "rate_limited"}), 429
                )
                resp.headers["Retry-After"] = str(lock_sec)
                set_csrf_cookie(resp, csrf_token)
                return resp
            
            resp = make_response(jsonify({"error": "invalid credentials", "message": "invalid credentials"}), 401)
            set_csrf_cookie(resp, csrf_token)
            return resp
        secrets_list = current_app.config.get("JWT_SECRETS") or []
        primary = _jwt_primary_secret()
        if not primary:
            return _json_error("server auth config missing", 500)
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
        session["role"] = _normalize_role(user.role)
        session["tenant_id"] = user.tenant_id
        # Keep display identity in session for app-shell badges/greetings.
        try:
            if getattr(user, "email", None):
                session["user_email"] = str(user.email)
            if getattr(user, "username", None):
                session["username"] = str(user.username)
            if getattr(user, "full_name", None):
                session["full_name"] = str(user.full_name)
        except Exception:
            pass
        # Enforce site-lock contract for non-superusers: bind active site when available
        try:
            role_norm = (session.get("role") or "").strip().lower()
            if role_norm != "superuser":
                # Prefer user.site_id; otherwise auto-select single site for tenant
                bound_site = None
                try:
                    sid_attr = getattr(user, "site_id", None)
                    bound_site = str(sid_attr) if sid_attr else None
                except Exception:
                    bound_site = None
                if (not bound_site) and user.tenant_id is not None:
                    # Pilot fallback: use kitchen_user_sites binding when users.site_id is unavailable.
                    try:
                        if role_norm == "kitchen":
                            from sqlalchemy import text as _t

                            row_k = db.execute(
                                _t(
                                    "SELECT site_id FROM kitchen_user_sites "
                                    "WHERE user_id=:uid AND tenant_id=:tid LIMIT 1"
                                ),
                                {"uid": int(user.id), "tid": int(user.tenant_id)},
                            ).fetchone()
                            if row_k and row_k[0]:
                                bound_site = str(row_k[0])
                    except Exception:
                        pass
                if (not bound_site) and user.tenant_id is not None:
                    try:
                        from .context import get_single_site_id_for_tenant as _one_site
                        bound_site = _one_site(int(user.tenant_id))
                    except Exception:
                        bound_site = None
                if bound_site:
                    session["site_id"] = bound_site
                    session["site_lock"] = True
                    try:
                        session["site_context_version"] = int(session.get("site_context_version") or 0) + 1
                    except Exception:
                        session["site_context_version"] = 1
                else:
                    # No active site could be derived; HTML flow returns 403 below for multi-site tenants,
                    # JSON/API flow will receive a 403 when we build response.
                    pass
        except Exception:
            pass
        # CSRF token issuance (double submit). Provide if not present already.
        # csrf_token already prepared above
        # Decide response based on request type: HTML form vs JSON client
        wants_html = False
        try:
            ctype = (request.content_type or "").lower()
            accept = (request.headers.get("Accept") or "").lower()
            if ("application/json" not in ctype) and (request.form) and ("text/html" in accept or not accept or "application/json" not in accept):
                wants_html = True
        except Exception:
            wants_html = False
        if wants_html:
            # HTML form flow: for non-superusers without active site, deny access instead of selector
            from flask import redirect, url_for
            target = None
            try:
                r = (session.get("role") or "").lower()
                if r == "superuser":
                    target = url_for("admin_ui.systemadmin_dashboard")
                elif r == "kitchen":
                    target = url_for("ui.kitchen_dashboard")
                elif r == "admin":
                    # If admin lacks an active site, return 403 HTML (no selector)
                    if not (session.get("site_id") or "").strip():
                        html = """<!doctype html><html lang='sv'><head><meta charset='utf-8'>
<title>Åtkomst nekad</title><meta name='robots' content='noindex'>
<style>body{font-family:system-ui;margin:3rem;color:#111}h1{font-size:1.8rem;margin-bottom:.5rem}p{margin:.25rem 0}</style>
</head><body><h1>Åtkomst nekad</h1>
<p>Ditt konto är inte kopplat till någon arbetsplats.</p>
<p>Kontakta systemadministratör.</p></body></html>"""
                        resp = make_response(html, 403)
                        resp.headers["Content-Type"] = "text/html; charset=utf-8"
                        set_csrf_cookie(resp, csrf_token)
                        return resp
                    else:
                        target = url_for("ui.admin_dashboard")
                elif r in ("unit_portal", "staff", "department"):
                    target = url_for("ui.portal_week")
                else:
                    target = url_for("ui.admin_dashboard")
            except Exception:
                target = "/"
            resp = redirect(target, code=302)
            set_csrf_cookie(resp, csrf_token)
            _emit_dev_auth_fingerprint("login_ok")
            return resp
        else:
            # JSON/API: if non-superuser and active site is missing, enforce 403
            try:
                role_norm = (session.get("role") or "").strip().lower()
                if role_norm != "superuser" and not (session.get("site_id") or "").strip():
                    resp = make_response(jsonify({"ok": False, "error": "forbidden", "message": "site_binding_required"}), 403)
                    set_csrf_cookie(resp, csrf_token)
                    return resp
            except Exception:
                pass
            
            resp = make_response(
                jsonify(
                    {
                        "ok": True,
                        "access_token": access,
                        "refresh_token": refresh,
                        "token_type": "Bearer",
                        "expires_in": DEFAULT_ACCESS_TTL,
                        "csrf_token": csrf_token,
                        "role": user.role,
                    }
                )
            )
            set_csrf_cookie(resp, csrf_token)
            _emit_dev_auth_fingerprint("login_ok")
            return resp
    finally:
        db.close()


@bp.get("/login")
def login_get():  # pragma: no cover
    """Render polished login UI template.

    GET /auth/login should serve the branded login page with spinner/logo.
    """
    vm = {"error": None}
    # Use render_template so context processors provide csrf helpers
    return render_template("login.html", vm=vm, error_message=None)


@bp.get("/forgot")
def forgot_password():  # pragma: no cover
    return render_template("auth_forgot.html")


@bp.post("/logout")
def logout():
    if os.getenv("STAGING_SIMPLE_AUTH", "0") in ("1", "true", "yes"):
        # Clear demo session quickly
        session.clear()
        resp = make_response(jsonify({"ok": True, "demo": True}))
        resp.delete_cookie("yp_demo")
        return resp
    # Accept refresh token or Authorization header, invalidate stored jti
    primary = _jwt_primary_secret()
    if not primary:
        return _json_error("server auth config missing", 500)
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
    if (
        os.getenv("STAGING_SIMPLE_AUTH", "0") in ("1", "true", "yes")
        and current_app.config.get("DEMO_AUTH_ENABLED") is True
        and not current_app.config.get("TESTING")
    ):
        return _json_error("refresh not supported in demo", 400)
    primary = _jwt_primary_secret()
    if not primary:
        return _json_error("server auth config missing", 500)
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
                "role": user.role,
            }
        )
    finally:
        db.close()


@bp.get("/me")
def me():
    # Prefer bearer token if supplied (stateless); fallback to session.
    primary = _jwt_primary_secret()
    if not primary:
        return _json_error("server auth config missing", 500)
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
    allow_destructive = (
        os.getenv("ALLOW_DESTRUCTIVE_DB", "0").lower() in ("1", "true", "yes")
        or os.getenv("YUPLAN_ALLOW_DESTRUCTIVE_DB", "0").lower() in ("1", "true", "yes")
    )
    reloader_flag = os.getenv("WERKZEUG_RUN_MAIN")
    reloader_ok = (reloader_flag is None) or (reloader_flag == "true")
    create_allowed = bool(current_app.config.get("TESTING")) and auto_create and allow_destructive and reloader_ok

    import inspect as _inspect

    def _dev_user_log(action: str) -> None:
        try:
            env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
            if env_val != "dev" and env_val != "development" and os.getenv("YUPLAN_DEV_HELPERS", "0").lower() not in ("1", "true", "yes"):
                return
            frame = _inspect.currentframe()
            caller = frame.f_back if frame else None
            func = caller.f_code.co_name if caller else "unknown"
            line = caller.f_lineno if caller else 0
            current_app.logger.info(
                "dev_user_mutation action=%s func=%s file=%s line=%s",
                action,
                func,
                __file__,
                line,
            )
        except Exception:
            pass

    try:
        current_app.logger.info("bootstrap_superuser: start auto_create=%s", auto_create)
    except Exception:
        pass

    try:
        db = get_session()
    except Exception:
        # DB session factory not initialized yet
        return

    try:
        # Ensure schema exists when allowed in dev
        if create_allowed:
            try:
                from .db import create_all as _create_all  # local import to avoid cycles
                try:
                    current_app.logger.warning("bootstrap_superuser: create_all requested")
                except Exception:
                    pass
                _create_all()
            except Exception:
                # Non-fatal; continue and let the next step decide
                pass
        elif auto_create:
            try:
                current_app.logger.warning(
                    "bootstrap_superuser: create_all blocked (ALLOW_DESTRUCTIVE_DB + WERKZEUG_RUN_MAIN required)"
                )
            except Exception:
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
        try:
            current_app.logger.info(
                "AUTH: seed_mode=bootstrap_env superuser_exists=%s will_update_password=%s",
                bool(has_user),
                False,
            )
        except Exception:
            pass
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
        _dev_user_log("insert_user")
        db.add(user)
        db.commit()
        try:
            current_app.logger.info("Bootstrap superuser created: %s", email)
        except Exception:
            pass
    finally:
        db.close()


# --- Dev Seed: Named Superuser (Henrik) ---
def ensure_dev_superuser_henrik():
    """Ensure a developer superuser exists for local runs.

    Controlled by env flags: if either DEV_CREATE_ALL or YUPLAN_SEED_HENRIK is truthy,
    create (or update) a superuser with the specified credentials. Safe no-op if tables
    are missing and auto-create not allowed.
    """
    import os as _os
    import inspect as _inspect
    from werkzeug.security import generate_password_hash as _gph

    def _dev_user_log(action: str) -> None:
        try:
            env_val = (_os.getenv("APP_ENV") or _os.getenv("FLASK_ENV") or "").lower()
            if env_val != "dev" and env_val != "development" and _os.getenv("YUPLAN_DEV_HELPERS", "0").lower() not in ("1", "true", "yes"):
                return
            frame = _inspect.currentframe()
            caller = frame.f_back if frame else None
            func = caller.f_code.co_name if caller else "unknown"
            line = caller.f_lineno if caller else 0
            current_app.logger.info(
                "dev_user_mutation action=%s func=%s file=%s line=%s",
                action,
                func,
                __file__,
                line,
            )
        except Exception:
            pass

    seed_enabled = (
        _os.getenv("YUPLAN_SEED_HENRIK", "0").lower() in ("1", "true", "yes")
        or _os.getenv("DEV_CREATE_ALL", "0").lower() in ("1", "true", "yes")
    )
    if not seed_enabled:
        return
    try:
        current_app.logger.info("dev_superuser_henrik: seed enabled")
    except Exception:
        pass
    try:
        db = get_session()
    except Exception:
        return
    try:
        # Optionally create schema
        try:
            dev_create_all = _os.getenv("DEV_CREATE_ALL", "0").lower() in ("1", "true", "yes")
            allow_destructive = (
                _os.getenv("ALLOW_DESTRUCTIVE_DB", "0").lower() in ("1", "true", "yes")
                or _os.getenv("YUPLAN_ALLOW_DESTRUCTIVE_DB", "0").lower() in ("1", "true", "yes")
            )
            reloader_flag = _os.getenv("WERKZEUG_RUN_MAIN")
            reloader_ok = (reloader_flag is None) or (reloader_flag == "true")
            create_allowed = bool(current_app.config.get("TESTING")) and dev_create_all and allow_destructive and reloader_ok
            if create_allowed:
                from .db import create_all as _create_all
                try:
                    current_app.logger.warning("dev_superuser_henrik: create_all requested")
                except Exception:
                    pass
                _create_all()
            elif dev_create_all:
                try:
                    current_app.logger.warning(
                        "dev_superuser_henrik: create_all blocked (ALLOW_DESTRUCTIVE_DB + WERKZEUG_RUN_MAIN required)"
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # Ensure basic tables exist by best-effort inspection
        try:
            from sqlalchemy import inspect as _sa_inspect  # type: ignore

            insp = _sa_inspect(db.bind)
            if not (insp.has_table("users") and insp.has_table("tenants")):
                return
        except Exception:
            pass
        # Seed tenant if missing
        try:
            t = db.query(Tenant).first()
            if not t:
                t = Tenant(name="Primary")
                db.add(t)
                db.flush()
        except Exception:
            return
        # Upsert Henrik user (DEV-only known-good). Allow override via env; default to Hen1024.
        email = "Henrik.Jonsson@Yuplan.se"
        import os as _os
        password = _os.getenv("YUPLAN_SEED_HENRIK_PASSWORD", "Hen1024")
        user = db.query(User).filter(User.email == email.lower()).first()
        seed_overwrite = _os.getenv("YUPLAN_DEV_SEED", "0").lower() in ("1", "true", "yes")
        try:
            current_app.logger.info(
                "AUTH: seed_mode=henrik superuser_exists=%s will_update_password=%s",
                bool(user),
                bool(user and seed_overwrite),
            )
        except Exception:
            pass
        if not user:
            _dev_user_log("insert_user")
            user = User(
                tenant_id=t.id,
                email=email.lower(),
                username=email.lower(),
                password_hash=_gph(password),
                role="superuser",
                full_name="Henrik Jonsson",
                is_active=True,
                unit_id=None,
            )
            db.add(user)
        else:
            # Keep idempotent but ensure role remains superuser
            user.role = "superuser"
            if not user.full_name:
                user.full_name = "Henrik Jonsson"
            # Always refresh password hash to match requested DEV credentials
            if seed_overwrite:
                _dev_user_log("update_user_password")
                try:
                    user.password_hash = _gph(password)
                except Exception:
                    pass
        db.commit()
    finally:
        db.close()


def ensure_dev_sync_superuser_from_env() -> None:
    """Ensure a dev superuser exists from env without overwriting passwords.

    Guarded by YUPLAN_DEV_SYNC_SUPERUSER=1 and non-testing environments.
    """
    if current_app.config.get("TESTING"):
        return
    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
    if env_val not in ("dev", "development"):
        return
    if os.getenv("YUPLAN_DEV_SYNC_SUPERUSER", "0").lower() not in ("1", "true", "yes"):
        return

    email = os.getenv("SUPERUSER_EMAIL") or ""
    password = os.getenv("SUPERUSER_PASSWORD") or ""
    if not email or not password:
        try:
            current_app.logger.info("AUTH: superuser_bootstrap action=skip_missing_env")
        except Exception:
            pass
        return

    normalized = email.strip().lower()
    try:
        db = get_session()
    except Exception:
        return
    try:
        try:
            from sqlalchemy import inspect as _sa_inspect  # type: ignore

            insp = _sa_inspect(db.bind)
            if not (insp.has_table("users") and insp.has_table("tenants")):
                return
        except Exception:
            pass

        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            tenant = db.query(Tenant).first()
        if not tenant:
            try:
                current_app.logger.info("AUTH: superuser_bootstrap action=skip_no_tenant")
            except Exception:
                pass
            return

        try:
            from sqlalchemy import func as _func

            user = (
                db.query(User)
                .filter(User.tenant_id == tenant.id, _func.lower(User.email) == normalized)
                .first()
            )
        except Exception:
            user = db.query(User).filter(User.tenant_id == tenant.id, User.email == normalized).first()

        if user:
            try:
                current_app.logger.info(
                    "AUTH: superuser_bootstrap action=exists email=%s",
                    normalized,
                )
            except Exception:
                pass
            return

        user = User(
            tenant_id=tenant.id,
            email=normalized,
            username=normalized,
            password_hash=generate_password_hash(password),
            role="superuser",
            full_name="Henrik Jonsson",
            is_active=True,
            unit_id=None,
        )
        db.add(user)
        db.commit()
        try:
            current_app.logger.info(
                "AUTH: superuser_bootstrap action=created email=%s",
                normalized,
            )
        except Exception:
            pass
    finally:
        db.close()
