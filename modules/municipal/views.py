from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session
from typing import Protocol, Any, TYPE_CHECKING

if TYPE_CHECKING:  # import only for typing to avoid circular
    from core.menu_service import MenuServiceDB

class HasMenuService(Protocol):
    menu_service: 'MenuServiceDB'

def _menu_service() -> 'MenuServiceDB':
    from core.menu_service import MenuServiceDB  # local import to avoid cycle
    svc = getattr(current_app, 'menu_service', None)
    if not isinstance(svc, MenuServiceDB):  # pragma: no cover
        raise RuntimeError('menu_service not bound to app')
    return svc

from core.auth import require_roles

bp = Blueprint("municipal", __name__, url_prefix="/municipal")

@bp.get("/ping")
def ping():  # pragma: no cover
    return {"module": "municipal", "ok": True}


@bp.get('/menu/week')
@require_roles('superuser','admin','unit_portal','cook')
def get_menu_week():
    try:
        week = int(request.args.get('week', ''))
        year = int(request.args.get('year', ''))
    except ValueError:
        return jsonify({"ok": False, "error": "invalid week/year"}), 400
    tenant_id_raw = session.get('tenant_id')
    if tenant_id_raw is None:
        return jsonify({"ok": False, "error": "missing tenant context"}), 400
    tenant_id = int(tenant_id_raw)
    svc = _menu_service()
    data = svc.get_week_view(tenant_id, week, year)
    return {"ok": True, **data}


@bp.post('/menu/variant')
@require_roles('superuser','admin','cook')
def set_menu_variant():
    payload = request.get_json(silent=True) or {}
    required = ['week', 'year', 'day', 'meal', 'variant_type']
    if not all(k in payload for k in required):
        return jsonify({"ok": False, "error": "missing fields"}), 400
    try:
        week = int(payload['week'])
        year = int(payload['year'])
    except ValueError:
        return jsonify({"ok": False, "error": "invalid week/year"}), 400
    day = payload['day']
    meal = payload['meal']
    variant_type = payload['variant_type']
    dish_id = payload.get('dish_id')
    tenant_id_raw = session.get('tenant_id')
    if tenant_id_raw is None:
        return jsonify({"ok": False, "error": "missing tenant context"}), 400
    tenant_id = int(tenant_id_raw)
    svc = _menu_service()
    # Ensure menu exists
    menu = svc.create_or_get_menu(tenant_id, week, year)
    try:
        mv_id = svc.set_variant(tenant_id, menu.id, day, meal, variant_type, dish_id)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return {"ok": True, "menu_id": menu.id, "menu_variant_id": mv_id}
