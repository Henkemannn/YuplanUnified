from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request, session

from .auth import require_roles
from .db import get_session
from .errors import ForbiddenError, NotFoundError, ValidationError
from .models import Note

bp = Blueprint('notes_api', __name__, url_prefix='/notes')

SAFE_READ_ROLES = ('superuser','admin','cook','unit_portal')
WRITE_ROLES = ('superuser','admin','cook','unit_portal')  # adjust if needed later


def _tenant_id():
    tid = session.get('tenant_id')
    if not tid:
        raise ValueError('tenant missing')
    return tid


def _serialize(note: Note):
    return {
        'id': note.id,
        'content': note.content,
        'private_flag': note.private_flag,
        'user_id': note.user_id,
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'updated_at': note.updated_at.isoformat() if note.updated_at else None,
    }

@bp.get('/')
@require_roles(*SAFE_READ_ROLES)
def list_notes():
    tid = _tenant_id()
    db = get_session()
    try:
        # Private notes are only visible to author or admins/superuser
        user_id = session.get('user_id')
        role = session.get('role')
        q = db.query(Note).filter(Note.tenant_id == tid)
        if role not in ('admin','superuser'):
            q = q.filter(((~Note.private_flag) | (Note.user_id == user_id)))  # type: ignore
        notes = q.order_by(Note.created_at.desc()).limit(500).all()
        return jsonify({'ok': True, 'notes': [_serialize(n) for n in notes]})
    finally:
        db.close()

@bp.post('/')
@require_roles(*WRITE_ROLES)
def create_note():
    tid = _tenant_id()
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    private_flag = bool(data.get('private_flag') or False)
    if not content:
        raise ValidationError("content required")
    db = get_session()
    try:
        note = Note(tenant_id=tid, user_id=session.get('user_id'), content=content, private_flag=private_flag)
        db.add(note)
        db.commit()
        db.refresh(note)
        return jsonify({'ok': True, 'note': _serialize(note)})
    finally:
        db.close()

@bp.put('/<int:note_id>')
@require_roles(*WRITE_ROLES)
def update_note(note_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        note = db.query(Note).filter(Note.id == note_id, Note.tenant_id == tid).first()
        if not note:
            raise NotFoundError("note not found")
        role = session.get('role')
        if note.user_id != session.get('user_id') and role not in ('admin','superuser'):
            raise ForbiddenError("forbidden")
        data = request.get_json(silent=True) or {}
        if 'content' in data:
            content = (data.get('content') or '').strip()
            if not content:
                raise ValidationError("content required")
            note.content = content
        if 'private_flag' in data:
            note.private_flag = bool(data.get('private_flag'))
        # Use timezone-aware UTC timestamp (avoids deprecation warning in Python 3.12+)
        note.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(note)
        return jsonify({'ok': True, 'note': _serialize(note)})
    finally:
        db.close()

@bp.delete('/<int:note_id>')
@require_roles(*WRITE_ROLES)
def delete_note(note_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        note = db.query(Note).filter(Note.id == note_id, Note.tenant_id == tid).first()
        if not note:
            raise NotFoundError("note not found")
        role = session.get('role')
        if note.user_id != session.get('user_id') and role not in ('admin','superuser'):
            raise ForbiddenError("forbidden")
        db.delete(note)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
