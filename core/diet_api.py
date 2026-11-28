from __future__ import annotations

from typing import cast

from flask import Blueprint, Response, current_app, jsonify, request, session

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
from .diet_scope import DietaryReferenceError
from .http_errors import bad_request, conflict, forbidden, not_found, unprocessable_entity
from .impersonation import get_impersonation

bp = Blueprint("diet", __name__, url_prefix="/diet")


def _site_scope() -> tuple[int, str] | Response:
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return bad_request("no_tenant_context")
    try:
        normalized_tenant_id = int(tenant_id)
    except (TypeError, ValueError):
        return bad_request("invalid_tenant_context")
    site_id = str(session.get("site_id") or "").strip()
    if not site_id:
        return forbidden("site_context_required")
    return normalized_tenant_id, site_id


def _legacy_unit_scope() -> int | Response:
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return bad_request("no_tenant_context")
    try:
        normalized_tenant_id = int(tenant_id)
    except (TypeError, ValueError):
        return bad_request("invalid_tenant_context")
    if session.get("role") != "superuser":
        return forbidden("unit_site_scope_unavailable")
    impersonation = get_impersonation()
    if not impersonation:
        return forbidden("impersonation_required")
    if impersonation.tenant_id != normalized_tenant_id:
        return forbidden("invalid_impersonation_context")
    return normalized_tenant_id


def _dietary_reference_response(error: DietaryReferenceError) -> Response:
    if error.status_code == 403:
        return forbidden(error.code)
    if error.status_code == 409:
        return conflict(error.code)
    if error.status_code == 400:
        return bad_request(error.code)
    raise RuntimeError(f"Unsupported dietary reference status: {error.status_code}")


@bp.get("/types")
@require_roles("superuser", "admin", "unit_portal", "cook")
def list_diet_types() -> DietTypeListResponse | ErrorResponse:
    scope = _site_scope()
    if isinstance(scope, Response):
        return cast(ErrorResponse, scope)
    tenant_id, site_id = scope
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    try:
        rows = svc.list_diet_types(tenant_id, site_id=site_id)
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    return cast(DietTypeListResponse, {"ok": True, "diet_types": rows})


@bp.get("/units")
@require_roles("superuser", "admin", "unit_portal", "cook")
def list_units() -> UnitListResponse | ErrorResponse:
    tenant_id = _legacy_unit_scope()
    if isinstance(tenant_id, Response):
        return cast(ErrorResponse, tenant_id)
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    return cast(UnitListResponse, {"ok": True, "units": svc.list_units(tenant_id)})


@bp.post("/types")
@require_roles("admin", "superuser")
def create_diet_type() -> DietTypeCreateResponse | ErrorResponse:
    # Superuser must impersonate for write
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    scope = _site_scope()
    if isinstance(scope, Response):
        return cast(ErrorResponse, scope)
    tenant_id, site_id = scope
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    default_select = bool(data.get("default_select"))
    if not name:
        # Legacy contract expects 400 with unified envelope for missing required field here
        from flask import jsonify as _json

        return _json({"ok": False, "error": "bad_request", "message": "missing name"}), 400  # type: ignore[return-value]
    # Hard guard: disallow purely numeric names
    if name.isdigit():
        return unprocessable_entity([{"field": "name", "msg": "must_not_be_numeric"}])  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    try:
        new_id = svc.create_diet_type(
            tenant_id, name, default_select, site_id=site_id
        )
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    return cast(DietTypeCreateResponse, {"ok": True, "diet_type_id": new_id})


@bp.post("/types/<int:diet_type_id>")
@require_roles("admin", "superuser")
def update_diet_type(diet_type_id: int) -> GenericOk | ErrorResponse:
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    scope = _site_scope()
    if isinstance(scope, Response):
        return cast(ErrorResponse, scope)
    tenant_id, site_id = scope
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    default_select = data.get("default_select")
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    # Validate name if provided
    if isinstance(name, str) and name.strip().isdigit():
        return unprocessable_entity([{"field": "name", "msg": "must_not_be_numeric"}])  # type: ignore[return-value]
    try:
        ok = svc.update_diet_type(
            tenant_id,
            diet_type_id,
            name=name,
            default_select=default_select,
            site_id=site_id,
        )
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    if not ok:
        return not_found("diet_type_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})


@bp.delete("/types/<int:diet_type_id>")
@require_roles("admin", "superuser")
def delete_diet_type(diet_type_id: int) -> GenericOk | ErrorResponse:
    if session.get("role") == "superuser" and not get_impersonation():
        return forbidden(
            "impersonation_required",
            problem_type="https://example.com/problems/impersonation-required",
        )  # type: ignore[return-value]
    scope = _site_scope()
    if isinstance(scope, Response):
        return cast(ErrorResponse, scope)
    tenant_id, site_id = scope
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    try:
        ok = svc.delete_diet_type(tenant_id, diet_type_id, site_id=site_id)
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    if not ok:
        return not_found("diet_type_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})


@bp.get("/assignments")
@require_roles("superuser", "admin", "unit_portal", "cook")
def get_assignments() -> AssignmentListResponse | ErrorResponse:
    tenant_id = _legacy_unit_scope()
    if isinstance(tenant_id, Response):
        return cast(ErrorResponse, tenant_id)
    unit_id = request.args.get("unit")
    if not unit_id:
        return jsonify({"ok": False, "error": "missing unit"}), 400  # type: ignore[return-value]
    try:
        uid = int(unit_id)
    except ValueError:
        return jsonify({"ok": False, "error": "invalid unit"}), 400  # type: ignore[return-value]
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    try:
        data = svc.list_assignments(uid, tenant_id=tenant_id)
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    return cast(AssignmentListResponse, {"ok": True, "unit_id": uid, "assignments": data})


@bp.post("/assignments")
@require_roles("admin", "superuser", "unit_portal")
def post_assignment() -> AssignmentCreateResponse | ErrorResponse:
    tenant_id = _legacy_unit_scope()
    if isinstance(tenant_id, Response):
        return cast(ErrorResponse, tenant_id)
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
    try:
        assignment_id = svc.set_assignment(
            unit_id, diet_type_id, count, tenant_id=tenant_id
        )
    except DietaryReferenceError as exc:
        return cast(ErrorResponse, _dietary_reference_response(exc))
    return cast(AssignmentCreateResponse, {"ok": True, "assignment_id": assignment_id})


@bp.delete("/assignments/<int:assignment_id>")
@require_roles("admin", "superuser", "unit_portal")
def delete_assignment(assignment_id: int) -> GenericOk | ErrorResponse:
    tenant_id = _legacy_unit_scope()
    if isinstance(tenant_id, Response):
        return cast(ErrorResponse, tenant_id)
    svc: DietService = current_app.diet_service  # type: ignore[attr-defined]
    ok = svc.delete_assignment(assignment_id, tenant_id=tenant_id)
    if not ok:
        return not_found("assignment_not_found")  # type: ignore[return-value]
    return cast(GenericOk, {"ok": True})
