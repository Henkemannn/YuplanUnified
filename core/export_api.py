from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO

from flask import Blueprint, Response, request, session, stream_with_context

"""Replace legacy role checks with core.app_authz.require_roles(RoleLike); remove manual 401/403 returns; rely on exceptions. Keep runtime responses unchanged (central handlers)."""

from .app_authz import require_roles
from .db import get_session
from .models import Note, Task
from .http_limits import limit

bp = Blueprint("export_api", __name__, url_prefix="/export")

ADMIN_ROLES = ("editor","admin")  # editor or admin can export; adapter maps legacy roles

def _tenant_id() -> int:
    tid = session.get("tenant_id")
    if not tid:
        raise ValueError("tenant missing")
    return int(tid)

def _csv_response(name: str, rows_iterable):
    sep = request.args.get("sep") or ","  # allow ?sep=; for regional Excel
    add_bom = request.args.get("bom", "0") == "1"
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")

    def generate():
        buf = StringIO()
        writer = csv.writer(buf, delimiter=sep, quoting=csv.QUOTE_MINIMAL)
        first = True
        for row in rows_iterable:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(row)
            data = buf.getvalue()
            if first:
                first = False
                if add_bom:
                    # Prepend UTF-8 BOM for Excel compatibility
                    data = "\ufeff" + data
            yield data

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{name}_{ts}.csv"'
        }
    )

@bp.get("/notes.csv")
@require_roles("editor","admin")
@limit(name="export_notes_csv", feature_flag="rate_limit_export", key_func=lambda: f"tenant:{session.get('tenant_id')}:{session.get('user_id')}")
def export_notes():
    tid = _tenant_id()
    db = get_session()
    try:
        q = db.query(Note).filter(Note.tenant_id == tid).order_by(Note.created_at.asc())
        def rows():
            yield ["id","created_at","updated_at","user_id","private_flag","content"]
            for n in q.yield_per(200):
                yield [
                    str(n.id),
                    n.created_at.isoformat() if n.created_at else "",
                    n.updated_at.isoformat() if n.updated_at else "",
                    str(n.user_id),
                    "1" if n.private_flag else "0",
                    (n.content or "").replace("\n"," ").strip(),
                ]
        return _csv_response("notes", rows())
    finally:
        db.close()

@bp.get("/tasks.csv")
@require_roles("editor","admin")
@limit(name="export_tasks_csv", feature_flag="rate_limit_export", key_func=lambda: f"tenant:{session.get('tenant_id')}:{session.get('user_id')}")
def export_tasks():
    tid = _tenant_id()
    db = get_session()
    try:
        q = db.query(Task).filter(Task.tenant_id == tid).order_by(Task.id.asc())
        def rows():
            yield ["id","created_at","updated_at","done","private_flag","assignee_id","creator_user_id","menu_id","dish_id","content"]
            for t in q.yield_per(200):
                c_at = getattr(t,"created_at",None)
                u_at = getattr(t,"updated_at",None)
                yield [
                    str(t.id),
                    c_at.isoformat() if c_at else "",
                    u_at.isoformat() if u_at else "",
                    "1" if getattr(t,"done",False) else "0",
                    "1" if getattr(t,"private_flag",False) else "0",
                    str(getattr(t,"assignee_id", "") or ""),
                    str(getattr(t,"creator_user_id", "") or ""),
                    str(getattr(t,"menu_id","") or ""),
                    str(getattr(t,"dish_id","") or ""),
                    (getattr(t,"content","") or "").replace("\n"," ").strip()
                ]
        return _csv_response("tasks", rows())
    finally:
        db.close()
