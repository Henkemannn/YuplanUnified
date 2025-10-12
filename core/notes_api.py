"""Notes API with pagination.

Replaces legacy role checks with `app_authz.require_roles`; enforces tenant scoping.
"""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request, session

from .app_authz import AuthzError, require_roles
from .db import get_session
from .deprecation import apply_deprecation
from .errors import NotFoundError, ValidationError
from .models import Note
from .pagination import make_page_response, parse_page_params
from .roles import RoleLike
from .telemetry import track_event  # optional metrics no-op if unavailable

bp = Blueprint("notes_api", __name__, url_prefix="/notes")

SAFE_READ_ROLES: tuple[RoleLike, RoleLike, RoleLike, RoleLike] = (
    "superuser",
    "admin",
    "cook",
    "unit_portal",
)
WRITE_ROLES: tuple[RoleLike, RoleLike, RoleLike, RoleLike] = (
    "superuser",
    "admin",
    "cook",
    "unit_portal",
)  # legacy; canonical mapping applied in require_roles


def _tenant_id():
    tid = session.get("tenant_id")
    if not tid:
        raise ValueError("tenant missing")
    return tid


def _serialize(note: Note):
    return {
        "id": note.id,
        "content": note.content,
        "private_flag": note.private_flag,
        "user_id": note.user_id,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@bp.get("/")
@require_roles("superuser", "admin", "cook", "unit_portal")
def list_notes():
    tid = _tenant_id()
    page_req = parse_page_params(dict(request.args))
    db = get_session()
    try:
        user_id = session.get("user_id")
        role = session.get("role")
        base_q = db.query(Note).filter(Note.tenant_id == tid)
        if role not in ("admin", "superuser"):
            base_q = base_q.filter((~Note.private_flag) | (Note.user_id == user_id))  # type: ignore
        # Stable deterministic ordering: created_at DESC, id DESC
        q = base_q.order_by(Note.created_at.desc(), Note.id.desc())
        total = q.count()
        start = (page_req["page"] - 1) * page_req["size"]
        items = q.offset(start).limit(page_req["size"]).all()
        resp = make_page_response([_serialize(n) for n in items], page_req, total)
        # Backwards compatibility: old clients/tests expect 'notes' list instead of 'items'
        if "items" in resp and "notes" not in resp:
            resp["notes"] = resp["items"]  # type: ignore[index]
        response = jsonify(resp)
        if "notes" in resp:
            apply_deprecation(response, aliases=["notes"], endpoint="notes")
        return response
    finally:
        db.close()


@bp.post("/")
@require_roles("superuser", "admin", "cook", "unit_portal")
def create_note():
    tid = _tenant_id()
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    private_flag = bool(data.get("private_flag") or False)
    if not content:
        raise ValidationError("content required")
    db = get_session()
    try:
        note = Note(
            tenant_id=tid,
            user_id=session.get("user_id"),
            content=content,
            private_flag=private_flag,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        # Telemetry: treat note creation as a 'registrering' style event for pilot visibility.
        avd_name = session.get("unit_name") or session.get(
            "avdelning"
        )  # legacy fallback keys if present
        track_event("registrering", avdelning=str(avd_name) if avd_name else None, maltid=None)
        return jsonify({"ok": True, "note": _serialize(note)})
    finally:
        db.close()


@bp.put("/<int:note_id>")
@require_roles("superuser", "admin", "cook", "unit_portal")
def update_note(note_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        note = db.query(Note).filter(Note.id == note_id, Note.tenant_id == tid).first()
        if not note:
            raise NotFoundError("note not found")
        role = session.get("role")
        if note.user_id != session.get("user_id") and role not in ("admin", "superuser"):
            # Ownership required unless elevated.
            raise AuthzError("forbidden", required="admin")
        data = request.get_json(silent=True) or {}
        if "content" in data:
            content = (data.get("content") or "").strip()
            if not content:
                raise ValidationError("content required")
            note.content = content
        if "private_flag" in data:
            note.private_flag = bool(data.get("private_flag"))
        # Use timezone-aware UTC timestamp (avoids deprecation warning in Python 3.12+)
        note.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(note)
        return jsonify({"ok": True, "note": _serialize(note)})
    finally:
        db.close()


@bp.delete("/<int:note_id>")
@require_roles("superuser", "admin", "cook", "unit_portal")
def delete_note(note_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        note = db.query(Note).filter(Note.id == note_id, Note.tenant_id == tid).first()
        if not note:
            raise NotFoundError("note not found")
        role = session.get("role")
        if note.user_id != session.get("user_id") and role not in ("admin", "superuser"):
            raise AuthzError("forbidden", required="admin")
        db.delete(note)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
