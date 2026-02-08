from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, jsonify, request, session

from core.auth import require_roles

from .api_types import (
    AssignmentCreateResponse,
    AssignmentListResponse,
    DietTypeCreateResponse,
    DietTypeListResponse,
    ErrorResponse,
    GenericOk,
    UnitListResponse,
)
from .diet_service import DietService
from .http_errors import bad_request, forbidden, not_found, unprocessable_entity
from .impersonation import get_impersonation

bp = Blueprint("diet", __name__, url_prefix="/diet")


@bp.get("/types")
@require_roles("superuser", "admin", "unit_portal", "cook")
def list_diet_types() -> DietTypeListResponse | ErrorResponse:
    from flask import session

    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    return cast(DietTypeListResponse, {"ok": True, "diet_types": svc.list_diet_types(tenant_id)})


@bp.get("/units")
@require_roles("superuser", "admin", "unit_portal", "cook")
def list_units() -> UnitListResponse | ErrorResponse:
    from flask import session

    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    return cast(UnitListResponse, {"ok": True, "units": svc.list_units(tenant_id)})


@bp.post("/types")
@require_roles("admin", "superuser")
def create_diet_type() -> DietTypeCreateResponse | ErrorResponse:
    tenant_id = session.get("tenant_id")
    # Superuser must impersonate for write
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    default_select = bool(data.get("default_select"))
    if not tenant_id:
        return bad_request("no_tenant_context")  # type: ignore[return-value]
    if not name:
        # Legacy contract expects 400 with unified envelope for missing required field here
        from flask import jsonify as _json

        return _json({"ok": False, "error": "bad_request", "message": "missing name"}), 400  # type: ignore[return-value]
    # Hard guard: disallow purely numeric names
    if name.isdigit():
        return unprocessable_entity([{"field": "name", "msg": "must_not_be_numeric"}])  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    new_id = svc.create_diet_type(tenant_id, name, default_select)
    return cast(DietTypeCreateResponse, {"ok": True, "diet_type_id": new_id})


@bp.post("/types/<int:diet_type_id>")
@require_roles("admin", "superuser")
def update_diet_type(diet_type_id: int) -> GenericOk | ErrorResponse:
    tenant_id = session.get("tenant_id")
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    default_select = data.get("default_select")
    if not tenant_id:
        return bad_request("no_tenant_context")  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    # Validate name if provided
    if isinstance(name, str) and name.strip().isdigit():
        return unprocessable_entity([{"field": "name", "msg": "must_not_be_numeric"}])  # type: ignore[return-value]
    ok = svc.update_diet_type(tenant_id, diet_type_id, name=name, default_select=default_select)
    if not ok:
        return not_found("diet_type_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})


@bp.delete("/types/<int:diet_type_id>")
@require_roles("admin", "superuser")
def delete_diet_type(diet_type_id: int) -> GenericOk | ErrorResponse:
    tenant_id = session.get("tenant_id")
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    if not tenant_id:
        return bad_request("no_tenant_context")  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.delete_diet_type(tenant_id, diet_type_id)
    if not ok:
        return not_found("diet_type_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})


@bp.get("/assignments")
@require_roles("superuser", "admin", "unit_portal", "cook")
def get_assignments() -> AssignmentListResponse | ErrorResponse:
    unit_id = request.args.get("unit")
    if not unit_id:
        return jsonify({"ok": False, "error": "missing unit"}), 400  # type: ignore[return-value]
    try:
        uid = int(unit_id)
    except ValueError:
        return jsonify({"ok": False, "error": "invalid unit"}), 400  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    data = svc.list_assignments(uid)
    return cast(AssignmentListResponse, {"ok": True, "unit_id": uid, "assignments": data})


@bp.post("/assignments")
@require_roles("admin", "superuser", "unit_portal")
def post_assignment() -> AssignmentCreateResponse | ErrorResponse:
    payload = request.get_json(silent=True) or {}
    for field in ["unit_id", "diet_type_id", "count"]:
        if field not in payload:
            return unprocessable_entity([{"field": field, "msg": "required"}])  # type: ignore[return-value]
    try:
        unit_id = int(payload["unit_id"])
        diet_type_id = int(payload["diet_type_id"])
        count = int(payload["count"])
    except ValueError:
        return bad_request("invalid_numeric_value")  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    assignment_id = svc.set_assignment(unit_id, diet_type_id, count)
    return cast(AssignmentCreateResponse, {"ok": True, "assignment_id": assignment_id})


@bp.delete("/assignments/<int:assignment_id>")
@require_roles("admin", "superuser", "unit_portal")
def delete_assignment(assignment_id: int) -> GenericOk | ErrorResponse:
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.delete_assignment(assignment_id)
    if not ok:
        return not_found("assignment_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})
