from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, session, url_for

from .auth import require_roles
from .db import get_session
from .models import Note, Task, Tenant, User

ui_bp = Blueprint("ui", __name__, template_folder="templates", static_folder="static")

SAFE_UI_ROLES = ("superuser", "admin", "cook", "unit_portal")


@ui_bp.get("/workspace")
@require_roles(*SAFE_UI_ROLES)
def workspace_ui():
    tid = session.get("tenant_id")
    user_id = session.get("user_id")
    role = session.get("role")
    db = get_session()
    try:
        # Notes visibility replicates API logic
        notes_q = db.query(Note).filter(Note.tenant_id == tid)
        if role not in ("admin", "superuser"):
            notes_q = notes_q.filter((~Note.private_flag) | (Note.user_id == user_id))  # type: ignore
        notes = notes_q.order_by(Note.created_at.desc()).limit(50).all()

        tasks_q = db.query(Task).filter(Task.tenant_id == tid).order_by(Task.id.desc()).limit(50)
        # Private tasks only to creator or admin/superuser
        if role not in ("admin", "superuser"):
            tasks_q = tasks_q.filter((~Task.private_flag) | (Task.creator_user_id == user_id))  # type: ignore
        tasks = tasks_q.all()

        # Resolve assignee names map (avoid N+1 for simplicity)
        user_ids = {t.assignee_id for t in tasks if t.assignee_id}
        if user_ids:
            users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        else:
            users = {}
        # Decorate for template
        tasks_view = []
        for t in tasks:
            ass_user = users.get(t.assignee_id) if t.assignee_id else None
            tasks_view.append(
                {
                    "id": t.id,
                    "title": getattr(t, "title", None),
                    "content": getattr(t, "title", None),
                    "status": "klar" if getattr(t, "done", False) else "öppen",
                    "assignee_name": ass_user.email if ass_user else None,
                }
            )
        return render_template("ui/notes_tasks.html", notes=notes, tasks=tasks_view)
    finally:
        db.close()


@ui_bp.get("/superuser/dashboard")
def superuser_dashboard():
    # UI-friendly guard: redirect unauthenticated/non-superuser to login instead of JSON envelope
    if not session.get("user_id") or session.get("role") != "superuser":
        try:
            return redirect(url_for("inline_ui.login_page"))
        except Exception:
            return redirect("/ui/login")
    # Render skeleton only, no API calls
    return render_template(
        "superuser/dashboard.html",
        ui_theme=(session.get("ui_theme") or None),
        ui_brand=(session.get("ui_brand") or None),
        dev=(current_app.config.get("DEBUG") or current_app.config.get("ENV") == "development"),
    )


@ui_bp.get("/tenants/new")
@require_roles("superuser")
def tenant_new_placeholder():  # lightweight placeholder
    return render_template("superuser/tenant_new.html")


@ui_bp.get("/feature-flags")
@require_roles("superuser")
def feature_flags_placeholder():
    return render_template("superuser/feature_flags.html")


@ui_bp.get("/audit")
@require_roles("superuser")
def audit_placeholder():
    return render_template("superuser/audit.html")


@ui_bp.get("/tenants/<int:tenant_id>")
@require_roles("superuser")
def tenant_show(tenant_id: int):
    db = get_session()
    try:
        t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not t:
            return redirect(url_for("ui.superuser_dashboard"))
        return render_template("tenants/show.html", tenant=t)
    finally:
        db.close()


@ui_bp.get("/tenants")
@require_roles("superuser")
def tenants_index():
    return render_template("tenants/index.html")
