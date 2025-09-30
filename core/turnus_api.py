from datetime import datetime

from flask import Blueprint, jsonify, request, session

from .auth import require_roles
from .turnus_service import TurnusService

bp = Blueprint('turnus_api', __name__, url_prefix='/turnus')
service = TurnusService()

def current_tenant_id():
    tid = session.get('tenant_id')
    if not tid:
        raise ValueError('tenant not in session')
    return tid

@bp.route('/templates', methods=['GET'])
@require_roles('admin','superuser')
def list_templates():
    tid = current_tenant_id()
    return jsonify(service.get_templates(tid))

@bp.route('/templates', methods=['POST'])
@require_roles('admin','superuser')
def create_template():
    tid = current_tenant_id()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    pattern_type = (data.get('pattern_type') or 'generic').strip() or 'generic'
    if not name:
        return jsonify({'error': 'name required'}), 400
    tpl_id = service.create_template(tid, name, pattern_type)
    return jsonify({'id': tpl_id})

@bp.route('/import', methods=['POST'])
@require_roles('admin','superuser')
def import_shifts():
    tid = current_tenant_id()
    data = request.get_json() or {}
    template_id = data.get('template_id')
    shifts = data.get('shifts') or []
    if not template_id:
        return jsonify({'error': 'template_id required'}), 400
    if not isinstance(shifts, list):
        return jsonify({'error': 'shifts must be list'}), 400
    result = service.import_shifts(tid, template_id, shifts)
    return jsonify(result)

@bp.route('/slots', methods=['GET'])
@require_roles('admin','superuser','unit_portal')
def query_slots():
    tid = current_tenant_id()
    df = request.args.get('from')
    dt = request.args.get('to')
    if not df or not dt:
        return jsonify({'error': 'from & to required (YYYY-MM-DD)'}), 400
    try:
        date_from = datetime.strptime(df, '%Y-%m-%d').date()
        date_to = datetime.strptime(dt, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'invalid date format'}), 400
    unit_ids_param = request.args.get('unit_ids')
    unit_ids = None
    if unit_ids_param:
        try:
            unit_ids = [int(x) for x in unit_ids_param.split(',') if x.strip()]
        except Exception:
            return jsonify({'error': 'invalid unit_ids'}), 400
    role = request.args.get('role')
    slots = service.query_slots(tid, date_from, date_to, unit_ids=unit_ids, role=role)
    return jsonify(slots)
