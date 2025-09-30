from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request, session

from .audit import log_task_status_transition
from .auth import require_roles
from .db import get_session
from .errors import ForbiddenError, NotFoundError, ValidationError
from .models import Task
from .rate_limit import RateLimitExceeded, allow, rate_limited_response

bp = Blueprint('tasks_api', __name__, url_prefix='/tasks')

READ_ROLES = ('superuser','admin','cook','unit_portal')
WRITE_ROLES = ('superuser','admin','cook','unit_portal')

ALLOWED_STATUS = {'todo','doing','blocked','done','cancelled'}


def _tenant_id():
    tid = session.get('tenant_id')
    if not tid:
        raise ValueError('tenant missing')
    return tid


def _serialize(t: Task):
    return {
        'id': t.id,
        'title': t.title,
        'task_type': t.task_type,
        'done': t.done,
        'status': getattr(t, 'status', 'done' if t.done else 'todo'),
        'menu_id': t.menu_id,
        'dish_id': t.dish_id,
        'private_flag': t.private_flag,
        'assignee_id': t.assignee_id,
        'creator_user_id': t.creator_user_id,
        'unit_id': t.unit_id,
        'created_at': t.created_at.isoformat() if getattr(t,'created_at',None) else None,
        'updated_at': t.updated_at.isoformat() if getattr(t,'updated_at',None) else None,
    }

@bp.get('/')
@require_roles(*READ_ROLES)
def list_tasks():
    tid = _tenant_id()
    db = get_session()
    try:
        q = db.query(Task).filter(Task.tenant_id == tid)
        menu_id = request.args.get('menu_id')
        dish_id = request.args.get('dish_id')
        if menu_id:
            try:
                q = q.filter(Task.menu_id == int(menu_id))
            except ValueError:
                raise ValidationError('invalid menu_id')
        if dish_id:
            try:
                q = q.filter(Task.dish_id == int(dish_id))
            except ValueError:
                raise ValidationError('invalid dish_id')
        role = session.get('role')
        user_id = session.get('user_id')
        if role not in ('admin','superuser'):
            q = q.filter((~Task.private_flag) | (Task.creator_user_id == user_id))  # type: ignore
        tasks = q.order_by(Task.id.desc()).limit(500).all()
        return jsonify({'ok': True, 'tasks': [_serialize(t) for t in tasks]})
    finally:
        db.close()

@bp.post('/')
@require_roles(*WRITE_ROLES)
def create_task():
    tid = _tenant_id()
    data = request.get_json(silent=True) or {}
    # Rate limit
    try:
        allow(tid, session.get('user_id'), 'tasks_mutations', 60, testing=current_app.config.get('TESTING', False))
    except RateLimitExceeded:
        return rate_limited_response()
    title = (data.get('title') or '').strip()
    task_type = (data.get('task_type') or 'prep').strip() or 'prep'
    if not title:
        raise ValidationError('title required')
    status = data.get('status')
    if status is not None:
        if status not in ALLOWED_STATUS:
            allowed_list = ', '.join(sorted(ALLOWED_STATUS))
            raise ValidationError(f"Invalid status '{status}'. Allowed: {allowed_list}.")
        done_val = (status == 'done')
    else:
        done_val = bool(data.get('done') or False)
        status = 'done' if done_val else 'todo'
    db = get_session()
    try:
        t = Task(
            tenant_id=tid,
            unit_id=data.get('unit_id'),
            task_type=task_type,
            title=title,
            done=done_val,
            status=status,
            menu_id=data.get('menu_id'),
            dish_id=data.get('dish_id'),
            private_flag=bool(data.get('private_flag') or False),
            assignee_id=data.get('assignee_id'),
            creator_user_id=session.get('user_id'),
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        from flask import make_response, url_for
        resp = make_response(jsonify({'ok': True, 'task': _serialize(t)}), 201)
        try:
            resp.headers['Location'] = url_for('tasks_api.get_task', task_id=t.id)
        except Exception:
            resp.headers['Location'] = f"/tasks/{t.id}"
        return resp
    finally:
        db.close()

@bp.get('/<int:task_id>')
@require_roles(*READ_ROLES)
def get_task(task_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tid).first()
        if not t:
            raise NotFoundError('task not found')
        role = session.get('role')
        user_id = session.get('user_id')
        if t.private_flag and t.creator_user_id != user_id and role not in ('admin','superuser'):
            raise ForbiddenError('forbidden')
        return jsonify({'ok': True, 'task': _serialize(t)})
    finally:
        db.close()

@bp.put('/<int:task_id>')
@require_roles(*WRITE_ROLES)
def update_task(task_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tid).first()
        if not t:
            raise NotFoundError('task not found')
        role = session.get('role')
        user_id = session.get('user_id')
        # Ownership enforcement: user can only modify own tasks (regardless of private flag)
        if role not in ('admin','superuser') and t.creator_user_id != user_id:
            raise ForbiddenError('forbidden')
        try:
            allow(tid, user_id, 'tasks_mutations', 60, testing=current_app.config.get('TESTING', False))
        except RateLimitExceeded:
            return rate_limited_response()
        data = request.get_json(silent=True) or {}
        if 'title' in data:
            title = (data.get('title') or '').strip()
            if not title:
                raise ValidationError('title required')
            t.title = title
        if 'status' in data:
            status = data.get('status')
            if status not in ALLOWED_STATUS:
                allowed_list = ', '.join(sorted(ALLOWED_STATUS))
                raise ValidationError(f"Invalid status '{status}'. Allowed: {allowed_list}.")
            old_status = getattr(t, 'status', 'done' if t.done else 'todo')
            t.done = (status == 'done')
            if hasattr(t, 'status'):
                t.status = status
            log_task_status_transition(db, t, old_status, status, user_id)
        if 'done' in data:
            t.done = bool(data.get('done'))
            if hasattr(t, 'status') and 'status' not in data:  # keep status in sync when legacy done used
                new_status = 'done' if t.done else 'todo'
                old_status = getattr(t, 'status', new_status)
                if hasattr(t, 'status'):
                    log_task_status_transition(db, t, old_status, new_status, user_id)
                    t.status = new_status
        if 'private_flag' in data:
            t.private_flag = bool(data.get('private_flag'))
        if 'assignee_id' in data:
            t.assignee_id = data.get('assignee_id')
        if 'menu_id' in data:
            t.menu_id = data.get('menu_id')
        if 'dish_id' in data:
            t.dish_id = data.get('dish_id')
        # touch updated_at if column exists
        if hasattr(t, 'updated_at'):
            try:
                t.updated_at = datetime.now(UTC)
            except Exception:
                pass
        db.commit()
        db.refresh(t)
        return jsonify({'ok': True, 'task': _serialize(t)})
    finally:
        db.close()

@bp.delete('/<int:task_id>')
@require_roles(*WRITE_ROLES)
def delete_task(task_id: int):
    tid = _tenant_id()
    db = get_session()
    try:
        t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tid).first()
        if not t:
            raise NotFoundError('task not found')
        role = session.get('role')
        user_id = session.get('user_id')
        if role not in ('admin','superuser') and t.creator_user_id != user_id:
            raise ForbiddenError('forbidden')
        try:
            allow(tid, user_id, 'tasks_mutations', 60, testing=current_app.config.get('TESTING', False))
        except RateLimitExceeded:
            return rate_limited_response()
        db.delete(t)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
