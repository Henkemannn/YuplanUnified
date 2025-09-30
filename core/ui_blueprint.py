from __future__ import annotations

from flask import Blueprint, render_template, session

from .auth import require_roles
from .db import get_session
from .models import Note, Task, User

ui_bp = Blueprint('ui', __name__)

SAFE_UI_ROLES = ('superuser','admin','cook','unit_portal')

@ui_bp.get('/workspace')
@require_roles(*SAFE_UI_ROLES)
def workspace_ui():
    tid = session.get('tenant_id')
    user_id = session.get('user_id')
    role = session.get('role')
    db = get_session()
    try:
        # Notes visibility replicates API logic
        notes_q = db.query(Note).filter(Note.tenant_id == tid)
        if role not in ('admin','superuser'):
            notes_q = notes_q.filter(((~Note.private_flag) | (Note.user_id == user_id)))  # type: ignore
        notes = notes_q.order_by(Note.created_at.desc()).limit(50).all()

        tasks_q = db.query(Task).filter(Task.tenant_id == tid).order_by(Task.id.desc()).limit(50)
        # Private tasks only to creator or admin/superuser
        if role not in ('admin','superuser'):
            tasks_q = tasks_q.filter(((~Task.private_flag) | (Task.creator_user_id == user_id)))  # type: ignore
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
            tasks_view.append({
                'id': t.id,
                'title': getattr(t,'title',None),
                'content': getattr(t,'title',None),
                'status': 'klar' if getattr(t,'done',False) else 'öppen',
                'assignee_name': ass_user.email if ass_user else None,
            })
        return render_template('notes_tasks.html', notes=notes, tasks=tasks_view)
    finally:
        db.close()
