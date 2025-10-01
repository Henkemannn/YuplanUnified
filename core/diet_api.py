from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_roles

from .diet_service import DietService

bp = Blueprint("diet", __name__, url_prefix="/diet")

@bp.get("/types")
@require_roles("superuser","admin","unit_portal","cook")
def list_diet_types():
    from flask import session
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    return {"ok": True, "diet_types": svc.list_diet_types(tenant_id)}

@bp.post("/types")
@require_roles("superuser","admin")
def create_diet_type():
    from flask import session
    tenant_id = session.get("tenant_id")
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    default_select = bool(data.get("default_select"))
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    if not name:
        return jsonify({"ok": False, "error": "missing name"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    new_id = svc.create_diet_type(tenant_id, name, default_select)
    return {"ok": True, "diet_type_id": new_id}

@bp.post("/types/<int:diet_type_id>")
@require_roles("superuser","admin")
def update_diet_type(diet_type_id: int):
    from flask import session
    tenant_id = session.get("tenant_id")
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    default_select = data.get("default_select")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.update_diet_type(tenant_id, diet_type_id, name=name, default_select=default_select)
    if not ok:
        return jsonify({"ok": False, "error": "not found"}), 404
    return {"ok": True}

@bp.delete("/types/<int:diet_type_id>")
@require_roles("superuser","admin")
def delete_diet_type(diet_type_id: int):
    from flask import session
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.delete_diet_type(tenant_id, diet_type_id)
    if not ok:
        return jsonify({"ok": False, "error": "not found"}), 404
    return {"ok": True}

@bp.get("/units")
@require_roles("superuser","admin","unit_portal","cook")
def list_units():
    from flask import session
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    return {"ok": True, "units": svc.list_units(tenant_id)}

@bp.get("/assignments")
@require_roles("superuser","admin","unit_portal","cook")
def get_assignments():
    unit_id = request.args.get("unit")
    if not unit_id:
        return jsonify({"ok": False, "error": "missing unit"}), 400
    try:
        uid = int(unit_id)
    except ValueError:
        return jsonify({"ok": False, "error": "invalid unit"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    data = svc.list_assignments(uid)
    return {"ok": True, "unit_id": uid, "assignments": data}

@bp.post("/assignments")
@require_roles("superuser","admin","unit_portal")
def post_assignment():
    payload = request.get_json(silent=True) or {}
    for field in ["unit_id","diet_type_id","count"]:
        if field not in payload:
            return jsonify({"ok": False, "error": "missing field " + field}), 400
    try:
        unit_id = int(payload["unit_id"])
        diet_type_id = int(payload["diet_type_id"])
        count = int(payload["count"])
    except ValueError:
        return jsonify({"ok": False, "error": "invalid numeric value"}), 400
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    assignment_id = svc.set_assignment(unit_id, diet_type_id, count)
    return {"ok": True, "assignment_id": assignment_id}

@bp.delete("/assignments/<int:assignment_id>")
@require_roles("superuser","admin","unit_portal")
def delete_assignment(assignment_id: int):
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.delete_assignment(assignment_id)
    if not ok:
        return jsonify({"ok": False, "error": "not found"}), 404
    return {"ok": True}
