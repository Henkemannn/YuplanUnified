from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .builder import BuilderFlow
from .builder.file_import import parse_builder_import_file
from .components import (
    CompositionService,
    InMemoryCompositionRepository,
    ComponentService,
    InMemoryComponentRepository,
)
from .menu import InMemoryCompositionAliasRepository

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


def _serialize_component(component) -> dict[str, Any]:
    return {
        "component_id": component.component_id,
        "component_name": component.canonical_name,
    }


def _serialize_library_composition(composition) -> dict[str, Any]:
    return {
        "composition_id": composition.composition_id,
        "composition_name": composition.composition_name,
    }


def _serialize_library_import_summary(summary) -> dict[str, Any]:
    return {
        "imported_count": summary.imported_count,
        "created_count": summary.created_count,
        "reused_count": summary.reused_count,
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
        "warnings": list(summary.warnings),
    }


def _run_library_import(lines: list[str]):
    flow = _get_builder_flow()
    return flow.import_library_text_lines(lines)


def _get_builder_flow() -> BuilderFlow:
    flow = current_app.extensions.get("builder_flow")
    if isinstance(flow, BuilderFlow):
        return flow

    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)

    flow = BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
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
        summary = _run_library_import(lines)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_library_import_summary(summary)})


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
                "file_type": preview.file_type,
                "line_count": len(preview.importable_lines),
                "lines": list(preview.importable_lines),
                "importable_lines": list(preview.importable_lines),
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
        summary = _run_library_import(lines)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "summary": _serialize_library_import_summary(summary)})


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


__all__ = ["bp", "_get_builder_flow"]