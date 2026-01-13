from __future__ import annotations

from flask import Blueprint, render_template, redirect, session, g, current_app
from flask import request, url_for

bp = Blueprint("home", __name__, template_folder="templates", static_folder="static")


@bp.get("/home")
def index():  # pragma: no cover - legacy landing retained under /home
    try:
        # Preserve original behavior under /home for manual access
        role = session.get("role")
        tid = session.get("tenant_id")
        if role and tid is not None:
            try:
                ff = getattr(g, "tenant_feature_flags", {})
                enabled = ff.get("ff.dashboard.enabled")
                if enabled is None:
                    reg = getattr(current_app, "feature_registry", None)
                    enabled = reg.enabled("ff.dashboard.enabled") if reg else False
                if enabled:
                    return redirect("/dashboard")
            except Exception:
                pass
        return render_template("home.html")
    except Exception:
        return redirect("/docs/")


@bp.route("/ui/login", methods=["GET", "POST"])
def ui_login():  # Simple HTML login that sets session directly or redirects to auth login
    from werkzeug.security import check_password_hash
    from .db import get_session as _get_session
    from .models import User
    from .auth import set_csrf_cookie as _set_csrf_cookie
    from flask import make_response
    if request.method == "POST":
        from .ident import canonicalize_identifier
        email = canonicalize_identifier(request.form.get("email") or "")
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", vm={"error": "Saknade uppgifter"})
        db = _get_session()
        try:
            identifier = email
            lookup_method = "email"
            user = db.query(User).filter(User.email == identifier).first()
            if not user:
                # Fallback: try username match for robustness
                try:
                    user = db.query(User).filter(User.username == identifier).first()
                    if user:
                        lookup_method = "username"
                except Exception:
                    user = None
            # Determine diagnostic result without changing UX
            result = "not_found"
            if user:
                is_inactive = (not bool(getattr(user, "is_active", True))) or (getattr(user, "deleted_at", None) is not None)
                if is_inactive:
                    result = "found_inactive"
                else:
                    if check_password_hash(user.password_hash, password):
                        result = "found_active_password_ok"
                    else:
                        result = "found_active_password_bad"
            try:
                current_app.logger.info({
                    "login_html": True,
                    "identifier": identifier,
                    "lookup_method": lookup_method,
                    "result": result,
                })
            except Exception:
                pass
            if (not user) or result != "found_active_password_ok":
                return render_template("login.html", vm={"error": "Ogiltiga uppgifter"})
            # Set session
            try:
                # Stabilize by clearing prior keys first
                session.clear()
            except Exception:
                pass
            session["user_id"] = user.id
            session["role"] = user.role
            session["tenant_id"] = user.tenant_id
            # Enrich session with identity for greetings
            try:
                session["user_email"] = user.email
                if getattr(user, "full_name", None):
                    session["full_name"] = user.full_name
            except Exception:
                pass
            # Enforce hard-binding for customer admins: if users.site_id is set, lock session to that site
            try:
                if user.role == "admin":
                    bound_site = getattr(user, "site_id", None)
                    if bound_site:
                        session["site_id"] = str(bound_site)
                        try:
                            session["site_lock"] = True
                        except Exception:
                            pass
                        try:
                            import uuid as _uuid
                            session["site_context_version"] = str(_uuid.uuid4())
                        except Exception:
                            import time as _t
                            session["site_context_version"] = str(int(_t.time()))
            except Exception:
                pass
            # Ensure CSRF cookie
            import secrets as _secrets
            tok = request.cookies.get("csrf_token") or _secrets.token_hex(16)
            # Role-based redirect to proper dashboards
            target = "/"
            if user.role == "superuser":
                target = "/ui/systemadmin/dashboard"
            elif user.role == "admin":
                target = "/ui/admin"
            else:
                # Fall back to existing start views
                target = "/ui/weekview"
            resp = make_response(redirect(target))
            _set_csrf_cookie(resp, tok)
            return resp
        finally:
            db.close()
    # For GET, prefer the polished auth login page and preserve `next` parameter
    try:
        next_url = (request.args.get("next") or "/").strip()
        from urllib.parse import quote
        enc_next = quote(next_url, safe="")
        # Redirect to /auth/login with URL-encoded next param for consistency with tests
        return redirect(url_for("auth.login_get") + (f"?next={enc_next}" if enc_next else ""))
    except Exception:
        # Fallback to legacy inline login template if routing fails
        return render_template("login.html", vm={})


# Dev helper: set session from current bearer or bootstrap superuser, then redirect
@bp.get("/ui/dev-login")
def ui_dev_login():  # pragma: no cover
    import os
    from flask import make_response
    # Only enable when explicitly opted-in
    if os.getenv("YUPLAN_DEV_HELPERS", "0").lower() not in ("1", "true", "yes"):
        return redirect(url_for("home.ui_login"))
    # Prefer current bearer header; else fall back to bootstrap superuser from env
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        # before_request will populate session; just redirect
        return redirect("/ui/systemadmin/customers")
    email = os.getenv("SUPERUSER_EMAIL") or "root@example.com"
    password = os.getenv("SUPERUSER_PASSWORD") or "changeme"
    from .db import get_session as _get_session
    from .models import User
    db = _get_session()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            return redirect(url_for("home.ui_login"))
        session["user_id"] = user.id
        session["role"] = user.role
        session["tenant_id"] = user.tenant_id
        from .auth import set_csrf_cookie as _set_csrf_cookie
        import secrets as _secrets
        tok = request.cookies.get("csrf_token") or _secrets.token_hex(16)
        resp = make_response(redirect("/ui/systemadmin/customers"))
        _set_csrf_cookie(resp, tok)
        return resp
    finally:
        db.close()
