from __future__ import annotations

from decimal import Decimal
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .builder import BuilderFlow
from .components import (
    CompositionService,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from .menu import ImportedMenuRow, InMemoryCompositionAliasRepository, MenuService

bp = Blueprint("builder_api", __name__, url_prefix="/api/builder")


def _bad_request(message: str):
    return jsonify({"ok": False, "error": "bad_request", "message": str(message)}), 400


def _require_json_object() -> dict[str, Any] | tuple[Any, int]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _bad_request("JSON object body required")
    return payload


def _require_str(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _optional_str(payload: dict[str, Any], field: str) -> str | None:
    raw = payload.get(field)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _maybe_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _decimal_to_json(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _serialize_composition_component(component) -> dict[str, Any]:
    return {
        "component_id": component.component_id,
        "component_name": component.component_name or component.component_id,
        "role": component.role,
        "sort_order": component.sort_order,
    }


def _serialize_composition(composition) -> dict[str, Any]:
    return {
        "composition_id": composition.composition_id,
        "composition_name": composition.composition_name,
        "library_group": composition.library_group,
        "components": [
            _serialize_composition_component(component) for component in composition.components
        ],
    }


def _serialize_menu(menu) -> dict[str, Any]:
    return {
        "menu_id": menu.menu_id,
        "site_id": menu.site_id,
        "week_key": menu.week_key,
        "version": menu.version,
        "status": menu.status,
    }


def _serialize_menu_detail(detail) -> dict[str, Any]:
    return {
        "menu_detail_id": detail.menu_detail_id,
        "menu_id": detail.menu_id,
        "day": detail.day,
        "meal_slot": detail.meal_slot,
        "composition_ref_type": detail.composition_ref_type,
        "composition_id": detail.composition_id,
        "unresolved_text": detail.unresolved_text,
        "note": detail.note,
        "sort_order": detail.sort_order,
    }


def _serialize_import_summary(summary) -> dict[str, Any]:
    return {
        "menu_id": summary.menu_id,
        "imported_count": summary.imported_count,
        "resolved_count": summary.resolved_count,
        "unresolved_count": summary.unresolved_count,
        "row_results": [
            {
                "day": row.day,
                "meal_slot": row.meal_slot,
                "raw_text": row.raw_text,
                "menu_detail_id": row.menu_detail_id,
                "kind": row.kind,
                "composition_id": row.composition_id,
                "unresolved_text": row.unresolved_text,
                "warnings": list(row.warnings),
            }
            for row in summary.row_results
        ],
        "warnings": list(summary.warnings),
    }


def _serialize_menu_cost_overview(overview) -> dict[str, Any]:
    return {
        "menu_id": overview.menu_id,
        "unresolved_count": overview.unresolved_count,
        "warnings": list(overview.warnings),
        "detail_costs": [
            {
                "menu_detail_id": detail.menu_detail_id,
                "menu_id": detail.menu_id,
                "composition_id": detail.composition_id,
                "target_portions": detail.target_portions,
                "total_cost": _decimal_to_json(detail.total_cost),
                "cost_per_portion": _decimal_to_json(detail.cost_per_portion),
                "warnings": list(detail.warnings),
                "composition_breakdown": (
                    {
                        "composition_id": detail.composition_breakdown.composition_id,
                        "target_portions": detail.composition_breakdown.target_portions,
                        "total_cost": _decimal_to_json(detail.composition_breakdown.total_cost),
                        "cost_per_portion": _decimal_to_json(
                            detail.composition_breakdown.cost_per_portion
                        ),
                        "warnings": list(detail.composition_breakdown.warnings),
                        "component_breakdowns": [
                            {
                                "component_id": component.component_id,
                                "recipe_id": component.recipe_id,
                                "scaled_cost": _decimal_to_json(component.scaled_cost),
                                "cost_per_portion": _decimal_to_json(
                                    component.cost_per_portion
                                ),
                                "warnings": list(component.warnings),
                            }
                            for component in detail.composition_breakdown.component_breakdowns
                        ],
                    }
                    if detail.composition_breakdown is not None
                    else None
                ),
            }
            for detail in overview.detail_costs
        ],
    }


def _get_builder_flow() -> BuilderFlow:
    flow = current_app.extensions.get("builder_flow")
    if isinstance(flow, BuilderFlow):
        return flow

    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    composition_service = CompositionService(repository=composition_repository)
    menu_service = MenuService(composition_repository=composition_repository)

    flow = BuilderFlow(
        composition_service=composition_service,
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
    )
    current_app.extensions["builder_flow"] = flow
    return flow


@bp.post("/compositions")
@require_roles("editor", "admin", "superuser")
def create_composition():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        composition = flow.create_composition(
            composition_id=_require_str(payload, "composition_id"),
            composition_name=_require_str(payload, "composition_name"),
            library_group=_optional_str(payload, "library_group"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)}), 201


@bp.get("/compositions")
@require_roles("editor", "admin", "superuser")
def list_compositions():
    try:
        flow = _get_builder_flow()
        compositions = flow.list_compositions()
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "count": len(compositions),
            "compositions": [
                _serialize_composition(composition)
                for composition in compositions
            ],
        }
    )


@bp.post("/compositions/<composition_id>/components")
@require_roles("editor", "admin", "superuser")
def add_component_to_composition(composition_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        composition = flow.add_component_to_composition(
            composition_id=str(composition_id),
            component_name=_require_str(payload, "component_name"),
            role=_optional_str(payload, "role"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.delete("/compositions/<composition_id>/components/<component_id>")
@require_roles("editor", "admin", "superuser")
def remove_component_from_composition(composition_id: str, component_id: str):
    try:
        flow = _get_builder_flow()
        composition = flow.remove_component_from_composition(
            composition_id=str(composition_id),
            component_id=str(component_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.patch("/compositions/<composition_id>/components/<component_id>")
@require_roles("editor", "admin", "superuser")
def rename_component_in_composition(composition_id: str, component_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        composition = flow.rename_component_in_composition(
            composition_id=str(composition_id),
            component_id=str(component_id),
            new_component_name=_require_str(payload, "component_name"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.post("/menus")
@require_roles("editor", "admin", "superuser")
def create_menu():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        menu = flow.create_menu(
            menu_id=_require_str(payload, "menu_id"),
            site_id=_require_str(payload, "site_id"),
            week_key=_require_str(payload, "week_key"),
            version=_maybe_int(payload.get("version"), field="version") or 1,
            status=_optional_str(payload, "status") or "draft",
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu": _serialize_menu(menu)}), 201


@bp.post("/menus/<menu_id>/import")
@require_roles("editor", "admin", "superuser")
def import_menu(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list) or not rows_payload:
        return _bad_request("rows must be a non-empty list")

    rows: list[ImportedMenuRow] = []
    try:
        for index, row_payload in enumerate(rows_payload):
            if not isinstance(row_payload, dict):
                raise ValueError(f"rows[{index}] must be an object")
            rows.append(
                ImportedMenuRow(
                    day=_require_str(row_payload, "day"),
                    meal_slot=_require_str(row_payload, "meal_slot"),
                    raw_text=_require_str(row_payload, "raw_text"),
                    note=_optional_str(row_payload, "note"),
                    sort_order=_maybe_int(row_payload.get("sort_order"), field="sort_order")
                    or 0,
                )
            )

        flow = _get_builder_flow()
        summary = flow.import_menu_rows(menu_id=str(menu_id), rows=rows)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_import_summary(summary)})


@bp.get("/menus/<menu_id>/unresolved")
@require_roles("editor", "admin", "superuser")
def list_unresolved(menu_id: str):
    try:
        flow = _get_builder_flow()
        unresolved = flow.list_unresolved_menu_details(str(menu_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "menu_id": str(menu_id),
            "count": len(unresolved),
            "unresolved": [_serialize_menu_detail(detail) for detail in unresolved],
        }
    )


@bp.get("/menus/<menu_id>/cost-overview")
@require_roles("editor", "admin", "superuser")
def menu_cost_overview(menu_id: str):
    raw_target = request.args.get("target_portions")
    try:
        target_portions = int(raw_target) if raw_target not in (None, "") else 1
    except Exception:
        return _bad_request("target_portions must be an integer")
    if target_portions <= 0:
        return _bad_request("target_portions must be > 0")

    try:
        flow = _get_builder_flow()
        overview = flow.get_menu_cost_overview(
            str(menu_id),
            default_target_portions=target_portions,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "overview": _serialize_menu_cost_overview(overview)})


@bp.post("/menus/<menu_id>/resolve")
@require_roles("editor", "admin", "superuser")
def resolve_menu_detail(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        menu_detail_id = _require_str(payload, "menu_detail_id")
        composition_id = _require_str(payload, "composition_id")

        flow = _get_builder_flow()
        updated = flow.resolve_menu_detail(
            menu_id=str(menu_id),
            menu_detail_id=menu_detail_id,
            composition_id=composition_id,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu_detail": _serialize_menu_detail(updated)})


@bp.post("/menus/<menu_id>/create-composition-from-row")
@require_roles("editor", "admin", "superuser")
def create_composition_from_row(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        menu_detail_id = _require_str(payload, "menu_detail_id")
        composition_name = _require_str(payload, "composition_name")

        flow = _get_builder_flow()
        composition, updated_menu_detail, warnings = flow.create_composition_from_unresolved_row(
            menu_id=str(menu_id),
            menu_detail_id=menu_detail_id,
            composition_name=composition_name,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "composition": _serialize_composition(composition),
            "menu_detail": _serialize_menu_detail(updated_menu_detail),
            "warnings": warnings,
        }
    ), 201


__all__ = ["bp", "_get_builder_flow"]