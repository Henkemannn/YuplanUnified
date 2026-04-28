from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .builder import BuilderFlow
from .builder.file_import import classify_builder_import_lines, parse_builder_import_file
from .builder_sqlite import (
    initialize_builder_sqlite,
    SQLiteComponentAliasRepository,
    SQLiteComponentRepository,
    SQLiteCompositionAliasRepository,
    SQLiteCompositionRepository,
)
from .components import (
    CompositionService,
    InMemoryCompositionRepository,
    ComponentService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    normalize_component_match_text,
)
from .menu import InMemoryCompositionAliasRepository

bp = Blueprint("builder_api", __name__, url_prefix="/api/builder")


@dataclass(frozen=True)
class _LibraryImportMetrics:
    created_component_count: int
    reused_component_count: int
    ignored_noise_count: int


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


def _require_int(payload: dict[str, Any], field: str) -> int:
    value = _maybe_int(payload.get(field), field=field)
    if value is None:
        raise ValueError(f"{field} is required")
    return value


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


def _optional_str_list(payload: dict[str, Any], field: str) -> list[str] | None:
    raw = payload.get(field)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a list")
    return [str(item or "").strip() for item in raw]


def _decimal_to_json(value: Decimal) -> str:
    return str(value)


def _serialize_recipe(recipe) -> dict[str, Any]:
    return {
        "recipe_id": recipe.recipe_id,
        "component_id": recipe.component_id,
        "recipe_name": recipe.recipe_name,
        "visibility": recipe.visibility,
        "is_default": recipe.is_default,
        "yield_portions": recipe.yield_portions,
        "notes": recipe.notes,
    }


def _serialize_recipe_for_component(recipe, *, primary_recipe_id: str | None) -> dict[str, Any]:
    payload = _serialize_recipe(recipe)
    payload["is_primary"] = str(recipe.recipe_id) == str(primary_recipe_id or "")
    return payload


def _serialize_recipe_ingredient_line(line) -> dict[str, Any]:
    amount_value = float(line.quantity_value)
    return {
        "recipe_ingredient_line_id": line.recipe_ingredient_line_id,
        "recipe_id": line.recipe_id,
        "ingredient_name": line.ingredient_name,
        "amount_value": amount_value,
        "amount_unit": line.quantity_unit,
        "note": line.note,
        "sort_order": line.sort_order,
        "trait_signals": list(line.trait_signals),
    }


def _serialize_recipe_scaling_preview(preview) -> dict[str, Any]:
    return {
        "recipe": {
            "recipe_id": preview.recipe_id,
            "component_id": preview.component_id,
            "recipe_name": preview.recipe_name,
            "visibility": preview.visibility,
            "notes": preview.notes,
        },
        "source_yield_portions": preview.source_yield_portions,
        "target_portions": preview.target_portions,
        "scaling_factor": _decimal_to_json(preview.scaling_factor),
        "ingredient_lines": [
            {
                "recipe_ingredient_line_id": line.recipe_ingredient_line_id,
                "ingredient_name": line.ingredient_name,
                "amount_unit": line.amount_unit,
                "original_amount_value": _decimal_to_json(line.original_amount_value),
                "scaled_amount_value": _decimal_to_json(line.scaled_amount_value),
                "note": line.note,
                "sort_order": line.sort_order,
            }
            for line in preview.ingredient_lines
        ],
    }


def _serialize_recipe_trait_signal_preview(preview) -> dict[str, Any]:
    return {
        "recipe": {
            "recipe_id": preview.recipe_id,
            "component_id": preview.component_id,
            "recipe_name": preview.recipe_name,
        },
        "trait_signals_present": list(preview.trait_signals_present),
        "ingredient_lines": [
            {
                "recipe_ingredient_line_id": line.recipe_ingredient_line_id,
                "ingredient_name": line.ingredient_name,
                "amount_unit": line.amount_unit,
                "note": line.note,
                "trait_signals": list(line.trait_signals),
            }
            for line in preview.ingredient_lines
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


def _serialize_component_declaration_readiness(readiness) -> dict[str, Any]:
    return {
        "component_id": readiness.component_id,
        "component_name": readiness.component_name,
        "primary_recipe_id": readiness.primary_recipe_id,
        "trait_signals_present": list(readiness.trait_signals_present),
        "conflict_preview": _serialize_diet_conflict_preview(readiness.conflict_preview),
        "ingredient_sources": [
            {
                "recipe_id": source.recipe_id,
                "recipe_ingredient_line_id": source.recipe_ingredient_line_id,
                "ingredient_name": source.ingredient_name,
                "trait_signals": list(source.trait_signals),
            }
            for source in readiness.ingredient_sources
        ],
        "warnings": list(readiness.warnings),
    }


def _serialize_composition_declaration_readiness(readiness) -> dict[str, Any]:
    return {
        "composition_id": readiness.composition_id,
        "composition_name": readiness.composition_name,
        "trait_signals_present": list(readiness.trait_signals_present),
        "conflict_preview": _serialize_diet_conflict_preview(readiness.conflict_preview),
        "components": [
            _serialize_component_declaration_readiness(component)
            for component in readiness.components
        ],
        "warnings": list(readiness.warnings),
    }


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


def _serialize_rendered_composition_text(model) -> dict[str, Any]:
    return {
        "composition_id": model.composition_id,
        "composition_name": model.composition_name,
        "text": model.text,
        "components": [
            {
                "component_id": item.component_id,
                "component_name": item.component_name,
                "role": item.role,
                "sort_order": item.sort_order,
                "text_token": item.text_token,
            }
            for item in model.rendered_components
        ],
    }


def _serialize_component(component) -> dict[str, Any]:
    return {
        "component_id": component.component_id,
        "component_name": component.canonical_name,
        "primary_recipe_id": component.primary_recipe_id,
    }


def _serialize_component_alias(alias) -> dict[str, Any]:
    return {
        "alias_id": alias.alias_id,
        "component_id": alias.component_id,
        "alias_text": alias.alias_text,
        "alias_norm": alias.alias_norm,
        "source": alias.source,
        "confidence": _decimal_to_json(alias.confidence) if isinstance(alias.confidence, Decimal) else alias.confidence,
    }


def _serialize_library_composition(composition) -> dict[str, Any]:
    return {
        "composition_id": composition.composition_id,
        "composition_name": composition.composition_name,
    }


def _serialize_library_import_summary(summary, metrics: _LibraryImportMetrics) -> dict[str, Any]:
    return {
        "imported_count": summary.imported_count,
        "created_count": summary.created_count,
        "reused_count": summary.reused_count,
        "created_composition_count": summary.created_count,
        "reused_composition_count": summary.reused_count,
        "created_component_count": metrics.created_component_count,
        "reused_component_count": metrics.reused_component_count,
        "ignored_noise_count": metrics.ignored_noise_count,
        "row_results": [
            {
                "raw_text": row.raw_text,
                "kind": row.kind,
                "composition_id": row.composition_id,
                "composition_name": row.composition_name,
                "matched_via": row.matched_via,
                "warnings": list(row.warnings),
            }
            for row in summary.row_results
        ],
        "component_review_items": list(summary.component_review_items),
        "warnings": list(summary.warnings),
    }


def _run_library_import(
    lines: list[str],
    *,
    ignored_noise_count: int = 0,
) -> tuple[Any, _LibraryImportMetrics]:
    flow = _get_builder_flow()
    known_component_ids = {
        str(component.component_id)
        for component in flow.list_library_components()
        if str(component.component_id).strip()
    }

    summary = flow.import_library_text_lines(lines)

    created_component_ids: set[str] = set()
    reused_component_ids: set[str] = set()
    seen_component_ids = set(known_component_ids)
    for row in summary.row_results:
        if str(row.matched_via or "").lower() != "created":
            continue
        composition = flow._composition_repository.get(row.composition_id)
        if composition is None:
            continue
        for component in composition.components:
            component_id = str(component.component_id or "").strip()
            if not component_id:
                continue
            if component_id in seen_component_ids:
                reused_component_ids.add(component_id)
            else:
                created_component_ids.add(component_id)
                seen_component_ids.add(component_id)

    metrics = _LibraryImportMetrics(
        created_component_count=len(created_component_ids),
        reused_component_count=len(reused_component_ids),
        ignored_noise_count=max(0, int(ignored_noise_count)),
    )
    return summary, metrics


def _get_builder_flow() -> BuilderFlow:
    flow = current_app.extensions.get("builder_flow")
    if isinstance(flow, BuilderFlow):
        return flow

    builder_db_path = str(current_app.config.get("BUILDER_DB_PATH") or "").strip()

    if builder_db_path:
        db_path = initialize_builder_sqlite(builder_db_path)
        component_repository = SQLiteComponentRepository(db_path=db_path)
        component_alias_repository = SQLiteComponentAliasRepository(db_path=db_path)
        composition_repository = SQLiteCompositionRepository(db_path=db_path)
        alias_repository = SQLiteCompositionAliasRepository(db_path=db_path)

        component_service = ComponentService(repository=component_repository)
        composition_service = CompositionService(repository=composition_repository)

        flow = BuilderFlow(
            component_service=component_service,
            composition_service=composition_service,
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            component_alias_repository=component_alias_repository,
        )
        current_app.extensions["builder_flow"] = flow
        return flow

    component_repository = InMemoryComponentRepository()
    component_alias_repository = InMemoryComponentAliasRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)

    flow = BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=component_alias_repository,
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
        composition_name = _require_str(payload, "composition_name")
        composition_id = _optional_str(payload, "composition_id")
        library_group = _optional_str(payload, "library_group")

        if composition_id:
            composition = flow.create_composition(
                composition_id=composition_id,
                composition_name=composition_name,
                library_group=library_group,
            )
        else:
            composition = flow.create_composition_with_generated_id(
                composition_name=composition_name,
                library_group=library_group,
                seed_components=True,
            )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)}), 201


@bp.post("/components")
@require_roles("editor", "admin", "superuser")
def create_component():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        component = flow.create_standalone_component(
            component_name=_require_str(payload, "component_name"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "component": _serialize_component(component)}), 201


@bp.get("/components")
@require_roles("editor", "admin", "superuser")
def list_reusable_components():
    query = request.args.get("q")
    try:
        flow = _get_builder_flow()
        components = flow.list_reusable_components_for_builder(query=query)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "count": len(components),
            "components": [_serialize_component(component) for component in components],
        }
    )


@bp.get("/components/<component_id>/aliases")
@require_roles("editor", "admin", "superuser")
def list_component_aliases(component_id: str):
    component_id_value = str(component_id or "").strip()
    if not component_id_value:
        return _bad_request("component_id is required")

    try:
        flow = _get_builder_flow()
        component = flow._component_service.get_component(component_id_value)
        if component is None:
            return _bad_request(f"component not found: {component_id_value}")
        aliases = flow.list_component_aliases(component_id=component_id_value)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "component_id": component_id_value,
            "count": len(aliases),
            "aliases": [_serialize_component_alias(alias) for alias in aliases],
        }
    )


@bp.post("/components/<component_id>/aliases")
@require_roles("editor", "admin", "superuser")
def create_component_alias_endpoint(component_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    component_id_value = str(component_id or "").strip()
    if not component_id_value:
        return _bad_request("component_id is required")

    try:
        flow = _get_builder_flow()
        alias = flow.add_component_alias(
            component_id=component_id_value,
            alias_text=_require_str(payload, "alias_text"),
            source=_optional_str(payload, "source") or "manual",
            confidence=payload.get("confidence", 1.0),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "alias": _serialize_component_alias(alias),
        }
    ), 201


@bp.get("/library")
@require_roles("editor", "admin", "superuser")
def list_library():
    try:
        flow = _get_builder_flow()
        components = flow.list_library_components()
        compositions = flow.list_library_compositions()
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "components": [_serialize_component(component) for component in components],
            "compositions": [
                _serialize_library_composition(composition)
                for composition in compositions
            ],
        }
    )


@bp.post("/import")
@require_roles("editor", "admin", "superuser")
def import_library_lines():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    lines: list[str] = []
    raw_text = payload.get("text")
    if raw_text is not None:
        lines.extend(str(raw_text).splitlines())

    raw_lines = payload.get("lines")
    if raw_lines is not None:
        if not isinstance(raw_lines, list):
            return _bad_request("lines must be a list")
        lines.extend(str(item or "") for item in raw_lines)

    try:
        summary, metrics = _run_library_import(lines)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_library_import_summary(summary, metrics)})


@bp.post("/import/preview-lines")
@require_roles("editor", "admin", "superuser")
def import_library_preview_lines():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        return _bad_request("lines must be a list")

    lines = [str(item or "") for item in raw_lines]
    classified = classify_builder_import_lines(lines)
    importable = [item for item in classified if item.classification == "importable_dish"]
    ignored = [item for item in classified if item.classification != "importable_dish"]

    return jsonify(
        {
            "ok": True,
            "preview": {
                "preview_contract_version": 2,
                "file_type": "pasted",
                "line_count": len(importable),
                "lines": [item.normalized_text for item in importable],
                "importable_lines": [item.normalized_text for item in importable],
                "importable_items": [
                    {
                        "preview_index": index,
                        "line": item.normalized_text,
                    }
                    for index, item in enumerate(importable)
                ],
                "ignored_lines": [
                    {
                        "raw_text": item.raw_text,
                        "normalized_text": item.normalized_text,
                        "classification": item.classification,
                        "reason": item.reason,
                    }
                    for item in ignored
                ],
                "classified_lines": [
                    {
                        "raw_text": item.raw_text,
                        "normalized_text": item.normalized_text,
                        "classification": item.classification,
                        "reason": item.reason,
                    }
                    for item in classified
                ],
                "counts": {
                    "total_classified": len(classified),
                    "importable": len(importable),
                    "ignored": len(ignored),
                },
            },
        }
    )


@bp.post("/import/file/preview")
@require_roles("editor", "admin", "superuser")
def import_library_file_preview():
    file_storage = request.files.get("file")
    if file_storage is None:
        return _bad_request("file is required")

    csv_column = request.form.get("csv_column")

    try:
        preview = parse_builder_import_file(file_storage, csv_column=csv_column)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "preview": {
                "preview_contract_version": 2,
                "file_type": preview.file_type,
                "line_count": len(preview.importable_lines),
                "lines": list(preview.importable_lines),
                "importable_lines": list(preview.importable_lines),
                "importable_items": [
                    {
                        "preview_index": index,
                        "line": line,
                    }
                    for index, line in enumerate(preview.importable_lines)
                ],
                "ignored_lines": [
                    {
                        "raw_text": item.raw_text,
                        "normalized_text": item.normalized_text,
                        "classification": item.classification,
                        "reason": item.reason,
                    }
                    for item in preview.ignored_lines
                ],
                "classified_lines": [
                    {
                        "raw_text": item.raw_text,
                        "normalized_text": item.normalized_text,
                        "classification": item.classification,
                        "reason": item.reason,
                    }
                    for item in preview.classified_lines
                ],
                "counts": {
                    "total_classified": len(preview.classified_lines),
                    "importable": len(preview.importable_lines),
                    "ignored": len(preview.ignored_lines),
                },
                "csv_column": preview.csv_column,
                "csv_column_index": preview.csv_column_index,
            },
        }
    )


@bp.post("/import/file/confirm")
@require_roles("editor", "admin", "superuser")
def import_library_file_confirm():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        return _bad_request("lines must be a list")
    lines = [str(item or "") for item in raw_lines]

    try:
        ignored_noise_count = _maybe_int(payload.get("ignored_noise_count"), field="ignored_noise_count")
        if ignored_noise_count is None:
            ignored_noise_count = 0
        if ignored_noise_count < 0:
            raise ValueError("ignored_noise_count must be >= 0")
        summary, metrics = _run_library_import(lines, ignored_noise_count=ignored_noise_count)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_library_import_summary(summary, metrics)})


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


@bp.post("/compositions/<composition_id>/components/attach")
@require_roles("editor", "admin", "superuser")
def attach_existing_component_to_composition(composition_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        composition = flow.attach_existing_component_to_composition(
            composition_id=str(composition_id),
            component_id=_require_str(payload, "component_id"),
            role=_optional_str(payload, "role"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.patch("/compositions/<composition_id>/components/reorder")
@require_roles("editor", "admin", "superuser")
def reorder_components_in_composition(composition_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    ordered_entries_raw = payload.get("ordered_entries")
    if not isinstance(ordered_entries_raw, list) or len(ordered_entries_raw) == 0:
        return _bad_request("ordered_entries must be a non-empty list")

    ordered_entries: list[tuple[str, int]] = []
    for index, item in enumerate(ordered_entries_raw):
        if not isinstance(item, dict):
            return _bad_request(f"ordered_entries[{index}] must be an object")
        component_id_value = str(item.get("component_id") or "").strip()
        if not component_id_value:
            return _bad_request(f"ordered_entries[{index}].component_id is required")
        sort_order_value = _maybe_int(item.get("sort_order"), field=f"ordered_entries[{index}].sort_order")
        if sort_order_value is None:
            return _bad_request(f"ordered_entries[{index}].sort_order is required")
        ordered_entries.append((component_id_value, int(sort_order_value)))

    try:
        flow = _get_builder_flow()
        composition = flow.reorder_components_in_composition(
            composition_id=str(composition_id),
            ordered_entries=ordered_entries,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.get("/compositions/<composition_id>/render/text")
@require_roles("editor", "admin", "superuser")
def render_composition_text(composition_id: str):
    try:
        flow = _get_builder_flow()
        model = flow.render_composition_text_model(composition_id=str(composition_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "rendered": _serialize_rendered_composition_text(model)})


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

    has_name = "component_name" in payload
    has_role = "role" in payload
    if not has_name and not has_role:
        return _bad_request("component_name or role is required")

    try:
        flow = _get_builder_flow()
        composition = None

        if has_name:
            composition = flow.rename_component_in_composition(
                composition_id=str(composition_id),
                component_id=str(component_id),
                new_component_name=_require_str(payload, "component_name"),
                role=_optional_str(payload, "role"),
                role_provided=has_role,
            )
        elif has_role:
            composition = flow.update_component_role_in_composition(
                composition_id=str(composition_id),
                component_id=str(component_id),
                role=_optional_str(payload, "role"),
            )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition": _serialize_composition(composition)})


@bp.post("/components/<component_id>/recipes")
@require_roles("editor", "admin", "superuser")
def create_component_recipe(component_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        recipe = flow.create_component_recipe(
            component_id=str(component_id),
            recipe_name=_require_str(payload, "recipe_name"),
            visibility=_optional_str(payload, "visibility") or "private",
            yield_portions=_require_int(payload, "yield_portions"),
            notes=_optional_str(payload, "notes"),
            recipe_id=_optional_str(payload, "recipe_id"),
            is_primary=bool(payload.get("is_primary", False)),
        )

        raw_lines = payload.get("ingredient_lines")
        if raw_lines is not None:
            if not isinstance(raw_lines, list):
                raise ValueError("ingredient_lines must be a list")
            for idx, item in enumerate(raw_lines):
                if not isinstance(item, dict):
                    raise ValueError(f"ingredient_lines[{idx}] must be an object")
                amount_value = item.get("amount_value")
                if amount_value is None:
                    amount_value = item.get("quantity_value")
                amount_unit = item.get("amount_unit")
                if amount_unit is None:
                    amount_unit = item.get("quantity_unit")

                flow.add_recipe_ingredient_line(
                    component_id=str(component_id),
                    recipe_id=recipe.recipe_id,
                    ingredient_name=_require_str(item, "ingredient_name"),
                    amount_value=amount_value,
                    amount_unit=str(amount_unit or "").strip(),
                    note=_optional_str(item, "note"),
                    sort_order=_maybe_int(item.get("sort_order"), field="sort_order") or 0,
                    trait_signals=_optional_str_list(item, "trait_signals"),
                    recipe_ingredient_line_id=_optional_str(item, "recipe_ingredient_line_id"),
                )

        recipe, lines = flow.get_component_recipe_detail(
            component_id=str(component_id),
            recipe_id=recipe.recipe_id,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return (
        jsonify(
            {
                "ok": True,
                "recipe": _serialize_recipe(recipe),
                "ingredient_lines": [_serialize_recipe_ingredient_line(line) for line in lines],
            }
        ),
        201,
    )


@bp.get("/components/<component_id>/recipes")
@require_roles("editor", "admin", "superuser")
def list_component_recipes(component_id: str):
    try:
        flow = _get_builder_flow()
        component, recipes = flow.list_component_recipes(component_id=str(component_id))
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "component": _serialize_component(component),
            "count": len(recipes),
            "recipes": [
                _serialize_recipe_for_component(
                    recipe,
                    primary_recipe_id=component.primary_recipe_id,
                )
                for recipe in recipes
            ],
        }
    )


@bp.patch("/components/<component_id>/recipes/primary")
@require_roles("editor", "admin", "superuser")
def set_component_primary_recipe(component_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        component = flow.set_component_primary_recipe(
            component_id=str(component_id),
            recipe_id=_optional_str(payload, "recipe_id"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "component": _serialize_component(component)})


@bp.post("/components/<component_id>/recipes/<recipe_id>/ingredients")
@require_roles("editor", "admin", "superuser")
def add_component_recipe_ingredient(component_id: str, recipe_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        amount_value = payload.get("amount_value")
        if amount_value is None:
            amount_value = payload.get("quantity_value")
        if amount_value is None:
            raise ValueError("amount_value is required")

        amount_unit = payload.get("amount_unit")
        if amount_unit is None:
            amount_unit = payload.get("quantity_unit")
        if str(amount_unit or "").strip() == "":
            raise ValueError("amount_unit is required")

        line = flow.add_recipe_ingredient_line(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
            ingredient_name=_require_str(payload, "ingredient_name"),
            amount_value=amount_value,
            amount_unit=str(amount_unit),
            note=_optional_str(payload, "note"),
            sort_order=_maybe_int(payload.get("sort_order"), field="sort_order") or 0,
            trait_signals=_optional_str_list(payload, "trait_signals"),
            recipe_ingredient_line_id=_optional_str(payload, "recipe_ingredient_line_id"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "ingredient_line": _serialize_recipe_ingredient_line(line)}), 201


@bp.patch("/components/<component_id>/recipes/<recipe_id>")
@require_roles("editor", "admin", "superuser")
def update_component_recipe(component_id: str, recipe_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        recipe = flow.update_component_recipe_metadata(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
            recipe_name=_require_str(payload, "recipe_name"),
            yield_portions=_require_int(payload, "yield_portions"),
            visibility=_optional_str(payload, "visibility"),
            notes=_optional_str(payload, "notes"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "recipe": _serialize_recipe(recipe)})


@bp.delete("/components/<component_id>/recipes/<recipe_id>")
@require_roles("editor", "admin", "superuser")
def delete_component_recipe(component_id: str, recipe_id: str):
    try:
        flow = _get_builder_flow()
        flow.delete_component_recipe(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True})


@bp.patch("/components/<component_id>/recipes/<recipe_id>/ingredients/<ingredient_line_id>")
@require_roles("editor", "admin", "superuser")
def update_component_recipe_ingredient(component_id: str, recipe_id: str, ingredient_line_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    try:
        flow = _get_builder_flow()
        amount_value = payload.get("amount_value")
        if amount_value is None:
            amount_value = payload.get("quantity_value")
        if amount_value is None:
            raise ValueError("amount_value is required")

        amount_unit = payload.get("amount_unit")
        if amount_unit is None:
            amount_unit = payload.get("quantity_unit")
        if str(amount_unit or "").strip() == "":
            raise ValueError("amount_unit is required")

        line = flow.update_recipe_ingredient_line(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
            recipe_ingredient_line_id=str(ingredient_line_id),
            ingredient_name=_require_str(payload, "ingredient_name"),
            amount_value=amount_value,
            amount_unit=str(amount_unit),
            note=_optional_str(payload, "note"),
            sort_order=_maybe_int(payload.get("sort_order"), field="sort_order") or 0,
            trait_signals=_optional_str_list(payload, "trait_signals"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "ingredient_line": _serialize_recipe_ingredient_line(line)})


@bp.delete("/components/<component_id>/recipes/<recipe_id>/ingredients/<ingredient_line_id>")
@require_roles("editor", "admin", "superuser")
def delete_component_recipe_ingredient(component_id: str, recipe_id: str, ingredient_line_id: str):
    try:
        flow = _get_builder_flow()
        flow.delete_recipe_ingredient_line(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
            recipe_ingredient_line_id=str(ingredient_line_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True})


@bp.get("/components/<component_id>/recipes/<recipe_id>")
@require_roles("editor", "admin", "superuser")
def get_component_recipe(component_id: str, recipe_id: str):
    try:
        flow = _get_builder_flow()
        recipe, lines = flow.get_component_recipe_detail(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "recipe": _serialize_recipe(recipe),
            "ingredient_lines": [_serialize_recipe_ingredient_line(line) for line in lines],
        }
    )


@bp.get("/components/<component_id>/recipes/<recipe_id>/scaling-preview")
@require_roles("editor", "admin", "superuser")
def get_component_recipe_scaling_preview(component_id: str, recipe_id: str):
    try:
        target_portions = _maybe_int(
            request.args.get("target_portions"),
            field="target_portions",
        )
        if target_portions is None:
            raise ValueError("target_portions is required")
        flow = _get_builder_flow()
        preview = flow.preview_component_recipe_scaling(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
            target_portions=int(target_portions),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "preview": _serialize_recipe_scaling_preview(preview)})


@bp.get("/components/<component_id>/recipes/<recipe_id>/trait-signals")
@require_roles("editor", "admin", "superuser")
def get_component_recipe_trait_signals(component_id: str, recipe_id: str):
    try:
        flow = _get_builder_flow()
        preview = flow.preview_component_recipe_trait_signals(
            component_id=str(component_id),
            recipe_id=str(recipe_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "preview": _serialize_recipe_trait_signal_preview(preview)})


@bp.get("/components/<component_id>/declaration-readiness")
@require_roles("editor", "admin", "superuser")
def get_component_declaration_readiness(component_id: str):
    try:
        include_declaration = _parse_bool_query_param(
            "include_declaration",
            default=bool(current_app.config.get("DECLARATION_READINESS_VISIBLE", False)),
        )
        if not include_declaration:
            return jsonify({"ok": True, "declaration_enabled": False, "readiness": None})

        flow = _get_builder_flow()
        readiness = flow.preview_component_declaration_readiness(
            component_id=str(component_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "declaration_enabled": True,
            "readiness": _serialize_component_declaration_readiness(readiness),
        }
    )


@bp.get("/compositions/<composition_id>/declaration-readiness")
@require_roles("editor", "admin", "superuser")
def get_composition_declaration_readiness(composition_id: str):
    try:
        include_declaration = _parse_bool_query_param(
            "include_declaration",
            default=bool(current_app.config.get("DECLARATION_READINESS_VISIBLE", False)),
        )
        if not include_declaration:
            return jsonify({"ok": True, "declaration_enabled": False, "readiness": None})

        flow = _get_builder_flow()
        readiness = flow.preview_composition_declaration_readiness(
            composition_id=str(composition_id),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify(
        {
            "ok": True,
            "declaration_enabled": True,
            "readiness": _serialize_composition_declaration_readiness(readiness),
        }
    )


__all__ = ["bp", "_get_builder_flow"]
