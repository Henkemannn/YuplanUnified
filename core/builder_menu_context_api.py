from __future__ import annotations

from decimal import Decimal
from typing import Any
import uuid

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .builder import BuilderFlow
from .builder_menu_context_flow import BuilderMenuContextFlow
from .components import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository
from .menu import ImportedMenuRow, MenuService

bp = Blueprint("builder_menu_context_api", __name__, url_prefix="/api/builder/menus")


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


def _parse_bool_query_param(name: str, *, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _decimal_to_json(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _serialize_menu(menu) -> dict[str, Any]:
    return {
        "menu_id": menu.menu_id,
        "title": getattr(menu, "title", None),
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


def _serialize_menu_row(row: dict[str, Any]) -> dict[str, Any]:
    ref_type = row.get("composition_ref_type")
    return {
        "menu_detail_id": row.get("menu_detail_id"),
        "menu_id": row.get("menu_id"),
        "day": row.get("day"),
        "meal_slot": row.get("meal_slot"),
        "composition_ref_type": ref_type,
        "is_unresolved": ref_type == "unresolved",
        "composition_id": row.get("composition_id"),
        "composition_name": row.get("composition_name"),
        "unresolved_text": row.get("unresolved_text"),
        "note": row.get("note"),
        "sort_order": row.get("sort_order"),
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
                                "cost_per_portion": _decimal_to_json(component.cost_per_portion),
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


def _serialize_diet_conflict_preview(preview) -> dict[str, Any]:
    return {
        "conflicts_present": list(preview.conflicts_present),
        "conflict_sources": [
            {
                "conflict_key": source.conflict_key,
                "triggering_trait_signals": list(source.triggering_trait_signals),
                "source_type": source.source_type,
                "source_id": source.source_id,
                "source_label": source.source_label,
            }
            for source in preview.conflict_sources
        ],
    }


def _serialize_menu_declaration_readiness(readiness) -> dict[str, Any]:
    return {
        "menu_id": readiness.menu_id,
        "trait_signals_present": list(readiness.trait_signals_present),
        "conflict_preview": _serialize_diet_conflict_preview(readiness.conflict_preview),
        "rows": [
            {
                "menu_detail_id": row.menu_detail_id,
                "composition_ref_type": row.composition_ref_type,
                "composition_id": row.composition_id,
                "composition_name": row.composition_name,
                "trait_signals_present": list(row.trait_signals_present),
                "conflict_preview": _serialize_diet_conflict_preview(row.conflict_preview),
                "components": [
                    {
                        "component_id": component.component_id,
                        "component_name": component.component_name,
                        "primary_recipe_id": component.primary_recipe_id,
                        "trait_signals_present": list(component.trait_signals_present),
                        "conflict_preview": _serialize_diet_conflict_preview(component.conflict_preview),
                        "ingredient_sources": [
                            {
                                "recipe_id": source.recipe_id,
                                "recipe_ingredient_line_id": source.recipe_ingredient_line_id,
                                "ingredient_name": source.ingredient_name,
                                "trait_signals": list(source.trait_signals),
                            }
                            for source in component.ingredient_sources
                        ],
                        "warnings": list(component.warnings),
                    }
                    for component in row.components
                ],
                "warnings": list(row.warnings),
            }
            for row in readiness.rows
        ],
        "warnings": list(readiness.warnings),
    }


def _get_menu_context_flow() -> BuilderMenuContextFlow:
    flow = current_app.extensions.get("builder_menu_context_flow")
    if isinstance(flow, BuilderMenuContextFlow):
        return flow

    builder_flow = current_app.extensions.get("builder_flow")
    if not isinstance(builder_flow, BuilderFlow):
        from .builder_api import _get_builder_flow

        builder_flow = _get_builder_flow()

    menu_service = current_app.extensions.get("builder_menu_service")
    if not isinstance(menu_service, MenuService):
        menu_service = MenuService(composition_repository=builder_flow._composition_repository)
        current_app.extensions["builder_menu_service"] = menu_service

    recipe_repository = current_app.extensions.get("builder_menu_recipe_repository")
    if not isinstance(recipe_repository, InMemoryRecipeRepository):
        recipe_repository = InMemoryRecipeRepository()
        current_app.extensions["builder_menu_recipe_repository"] = recipe_repository

    ingredient_repository = current_app.extensions.get("builder_menu_ingredient_repository")
    if not isinstance(ingredient_repository, InMemoryRecipeIngredientLineRepository):
        ingredient_repository = InMemoryRecipeIngredientLineRepository()
        current_app.extensions["builder_menu_ingredient_repository"] = ingredient_repository

    flow = BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=builder_flow._composition_repository,
        alias_repository=builder_flow._alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    current_app.extensions["builder_menu_context_flow"] = flow
    return flow


@bp.post("")
@require_roles("editor", "admin", "superuser")
def create_menu():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_menu_context_flow()
        generated_menu_id = f"menu_{uuid.uuid4().hex[:8]}"
        menu = flow.create_menu(
            menu_id=_optional_str(payload, "menu_id") or generated_menu_id,
            title=_optional_str(payload, "title") or _optional_str(payload, "name"),
            site_id=_require_str(payload, "site_id"),
            week_key=_require_str(payload, "week_key"),
            version=_maybe_int(payload.get("version"), field="version") or 1,
            status=_optional_str(payload, "status") or "draft",
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu": _serialize_menu(menu)}), 201


@bp.get("")
@require_roles("editor", "admin", "superuser")
def list_menus():
    flow = _get_menu_context_flow()
    menus = flow.list_menus()
    return jsonify(
        {
            "ok": True,
            "count": len(menus),
            "menus": [_serialize_menu(menu) for menu in menus],
        }
    )


@bp.post("/<menu_id>/rows")
@require_roles("editor", "admin", "superuser")
def add_composition_menu_row(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_menu_context_flow()
        detail = flow.add_composition_menu_row(
            menu_id=str(menu_id),
            menu_detail_id=_optional_str(payload, "menu_detail_id"),
            day=_require_str(payload, "day"),
            meal_slot=_require_str(payload, "meal_slot"),
            composition_id=_require_str(payload, "composition_id"),
            note=_optional_str(payload, "note"),
            sort_order=_maybe_int(payload.get("sort_order"), field="sort_order") or 0,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu_detail": _serialize_menu_detail(detail)}), 201


@bp.get("/<menu_id>/rows")
@require_roles("editor", "admin", "superuser")
def list_menu_rows(menu_id: str):
    try:
        flow = _get_menu_context_flow()
        rows = flow.list_menu_rows(str(menu_id))
        grouped = flow.list_menu_rows_grouped(str(menu_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "menu_id": str(menu_id),
            "count": len(rows),
            "rows": [_serialize_menu_row(row) for row in rows],
            "groups": [
                {
                    "day": group.get("day"),
                    "meal_slot": group.get("meal_slot"),
                    "count": group.get("count"),
                    "rows": [_serialize_menu_row(row) for row in (group.get("rows") or [])],
                }
                for group in grouped
            ],
        }
    )


@bp.get("/<menu_id>/adapter/compositions")
@require_roles("editor", "admin", "superuser")
def get_menu_composition_adapter_payload(menu_id: str):
    menu_detail_id = str(request.args.get("menu_detail_id") or "").strip() or None
    try:
        flow = _get_menu_context_flow()
        payload = flow.get_menu_composition_adapter_payload(
            str(menu_id),
            menu_detail_id=menu_detail_id,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "payload": payload})


@bp.get("/<menu_id>/adapter/compositions/grouped")
@require_roles("editor", "admin", "superuser")
def get_menu_composition_grouped_adapter_payload(menu_id: str):
    try:
        flow = _get_menu_context_flow()
        payload = flow.get_menu_composition_grouped_adapter_payload(str(menu_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "payload": payload})


@bp.get("/<menu_id>/adapter/compositions/production-shape")
@require_roles("editor", "admin", "superuser")
def get_menu_composition_production_shape_adapter_payload(menu_id: str):
    try:
        flow = _get_menu_context_flow()
        payload = flow.get_menu_composition_production_shape_adapter_payload(str(menu_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "payload": payload})


@bp.patch("/<menu_id>/rows/<menu_detail_id>")
@require_roles("editor", "admin", "superuser")
def update_composition_menu_row(menu_id: str, menu_detail_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_menu_context_flow()
        detail = flow.update_composition_menu_row(
            menu_id=str(menu_id),
            menu_detail_id=str(menu_detail_id),
            day=_require_str(payload, "day"),
            meal_slot=_require_str(payload, "meal_slot"),
            composition_id=_require_str(payload, "composition_id"),
            note=_optional_str(payload, "note"),
            sort_order=_maybe_int(payload.get("sort_order"), field="sort_order"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu_detail": _serialize_menu_detail(detail)})


@bp.delete("/<menu_id>/rows/<menu_detail_id>")
@require_roles("editor", "admin", "superuser")
def delete_menu_row(menu_id: str, menu_detail_id: str):
    try:
        flow = _get_menu_context_flow()
        flow.delete_menu_row(menu_id=str(menu_id), menu_detail_id=str(menu_detail_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu_id": str(menu_id), "menu_detail_id": str(menu_detail_id)})


@bp.post("/<menu_id>/import")
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

        flow = _get_menu_context_flow()
        summary = flow.import_menu_rows(menu_id=str(menu_id), rows=rows)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_import_summary(summary)})


@bp.get("/<menu_id>/unresolved")
@require_roles("editor", "admin", "superuser")
def list_unresolved(menu_id: str):
    try:
        flow = _get_menu_context_flow()
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


@bp.get("/<menu_id>/cost-overview")
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
        flow = _get_menu_context_flow()
        overview = flow.get_menu_cost_overview(
            str(menu_id),
            default_target_portions=target_portions,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "overview": _serialize_menu_cost_overview(overview)})


@bp.get("/<menu_id>/declaration-readiness")
@require_roles("editor", "admin", "superuser")
def menu_declaration_readiness(menu_id: str):
    try:
        include_declaration = _parse_bool_query_param(
            "include_declaration",
            default=bool(current_app.config.get("DECLARATION_READINESS_VISIBLE", False)),
        )
        if not include_declaration:
            return jsonify({"ok": True, "declaration_enabled": False, "readiness": None})

        flow = _get_menu_context_flow()
        readiness = flow.get_menu_declaration_readiness(str(menu_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "declaration_enabled": True,
            "readiness": _serialize_menu_declaration_readiness(readiness),
        }
    )


@bp.post("/<menu_id>/resolve")
@require_roles("editor", "admin", "superuser")
def resolve_menu_detail(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        menu_detail_id = _require_str(payload, "menu_detail_id")
        composition_id = _require_str(payload, "composition_id")

        flow = _get_menu_context_flow()
        updated = flow.resolve_menu_detail(
            menu_id=str(menu_id),
            menu_detail_id=menu_detail_id,
            composition_id=composition_id,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "menu_detail": _serialize_menu_detail(updated)})


@bp.post("/<menu_id>/create-composition-from-row")
@require_roles("editor", "admin", "superuser")
def create_composition_from_row(menu_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        menu_detail_id = _require_str(payload, "menu_detail_id")
        composition_name = _require_str(payload, "composition_name")

        flow = _get_menu_context_flow()
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
            "composition": {
                "composition_id": composition.composition_id,
                "composition_name": composition.composition_name,
                "library_group": composition.library_group,
                "components": [
                    {
                        "component_id": component.component_id,
                        "component_name": component.component_name or component.component_id,
                        "role": component.role,
                        "sort_order": component.sort_order,
                    }
                    for component in composition.components
                ],
            },
            "menu_detail": _serialize_menu_detail(updated_menu_detail),
            "warnings": warnings,
        }
    ), 201


__all__ = ["bp", "_get_menu_context_flow"]
