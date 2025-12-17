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
def ui_login():  # Simple HTML login that sets session directly
    from werkzeug.security import check_password_hash
    from .db import get_session as _get_session
    from .models import User
    from .auth import set_csrf_cookie as _set_csrf_cookie
    from flask import make_response
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", vm={"error": "Saknade uppgifter"})
        db = _get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user or not check_password_hash(user.password_hash, password):
                return render_template("login.html", vm={"error": "Ogiltiga uppgifter"})
            # Set session
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
