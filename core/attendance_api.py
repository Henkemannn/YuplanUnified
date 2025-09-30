from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_roles

from .attendance_service import AttendanceService

bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@bp.put('/')
@require_roles('superuser','admin','unit_portal','cook')
def put_attendance():
    data = request.get_json(silent=True) or {}
    required = ['unit_id','date','meal','count']
    if not all(k in data for k in required):
        return jsonify({'ok': False, 'error': 'missing fields'}), 400
    try:
        unit_id = int(data['unit_id'])
        day_date = date.fromisoformat(data['date'])
        count = int(data['count'])
        meal = data['meal']
    except Exception:
        return jsonify({'ok': False, 'error': 'invalid field format'}), 400
    svc: AttendanceService = current_app.attendance_service  # type: ignore[attr-defined]
    row_id = svc.set_attendance(unit_id, day_date, meal, count)
    return {'ok': True, 'attendance_id': row_id}

@bp.get('/summary')
@require_roles('superuser','admin','unit_portal','cook')
def get_summary():
    try:
        unit_id = int(request.args.get('unit_id',''))
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        if not (unit_id and start_str and end_str):
            return jsonify({'ok': False, 'error':'missing params'}), 400
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except Exception:
        return jsonify({'ok': False, 'error': 'invalid date format'}), 400
    svc: AttendanceService = current_app.attendance_service  # type: ignore[attr-defined]
    data = svc.summary(unit_id, start, end)
    return {'ok': True, **data}
