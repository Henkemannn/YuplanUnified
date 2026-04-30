from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
import uuid

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .builder import BuilderFlow
from .builder_menu_context_flow import BuilderMenuContextFlow
from .builder.file_import import (
    classify_builder_import_lines,
    parse_builder_import_file,
    sanitize_builder_import_text,
    suggest_component_category,
    suggest_components_from_import_dish_name,
)
from .builder_sqlite import (
    clear_builder_sqlite_data,
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
from .menu import InMemoryCompositionAliasRepository, resolve_composition_reference

bp = Blueprint("builder_api", __name__, url_prefix="/api/builder")


@dataclass(frozen=True)
class _LibraryImportMetrics:
    created_component_count: int
    reused_component_count: int
    ignored_noise_count: int


def _bad_request(message: str):
    return jsonify({"ok": False, "error": "bad_request", "message": str(message)}), 400


def _conflict(message: str, **payload):
    body = {"ok": False, "error": "conflict", "message": str(message)}
    body.update(payload)
    return jsonify(body), 409


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


def _build_import_review_drafts(lines: list[str]) -> list[dict[str, Any]]:
    flow = _get_builder_flow()
    classified = classify_builder_import_lines(lines)
    drafts: list[dict[str, Any]] = []
    for index, item in enumerate(classified):
        is_importable = item.classification == "importable_dish"
        normalized_name = sanitize_builder_import_text(item.normalized_text)

        item_type = "ignore"
        components: list[dict[str, str]] = []
        hints: list[dict[str, Any]] = []
        if is_importable and normalized_name:
            component_suggestions = suggest_components_from_import_dish_name(normalized_name)
            item_type = "dish" if len(component_suggestions) >= 2 else "component"
            components = [{"name": name} for name in component_suggestions]
            for name in component_suggestions:
                match = flow.match_component_name(name)
                if str(match.status or "") in {"exact_match", "alias_match", "possible_match"}:
                    hints.append(
                        {
                            "component_name": name,
                            "match_status": match.status,
                            "possible_matches": [
                                {
                                    "component_id": candidate.component_id,
                                    "component_name": candidate.component_name,
                                    "score": candidate.score,
                                }
                                for candidate in match.possible_matches
                            ],
                        }
                    )

        drafts.append(
            {
                "draft_id": str(index),
                "selected": bool(is_importable),
                "item_type": item_type,
                "raw_text": item.raw_text,
                "name": normalized_name,
                "components": components,
                "hints": hints,
                "classification": item.classification,
                "reason": item.reason,
            }
        )
    return drafts


def _publish_review_drafts(items: list[dict[str, Any]]) -> dict[str, Any]:
    flow = _get_builder_flow()
    known_component_ids = {
        str(component.component_id)
        for component in flow.list_library_components()
        if str(component.component_id).strip()
    }

    created_component_count = 0
    reused_component_count = 0
    created_composition_count = 0
    reused_composition_count = 0
    ignored_count = 0
    imported_count = 0
    row_results: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            warnings.append(f"item {index}: skipped invalid object")
            continue

        selected = bool(raw_item.get("selected", True))
        item_type = str(raw_item.get("item_type") or "ignore").strip().lower()
        source_text = str(raw_item.get("raw_text") or "").strip()
        name = sanitize_builder_import_text(str(raw_item.get("name") or ""))

        if not selected or item_type == "ignore":
            ignored_count += 1
            continue

        if not name:
            ignored_count += 1
            warnings.append(f"item {index}: empty name after cleanup")
            continue

        imported_count += 1

        if item_type == "component":
            component = flow.create_standalone_component(name)
            if component.component_id in known_component_ids:
                reused_component_count += 1
                matched_via = "existing"
            else:
                created_component_count += 1
                known_component_ids.add(component.component_id)
                matched_via = "created"

            row_results.append(
                {
                    "raw_text": source_text or name,
                    "kind": "component",
                    "composition_id": None,
                    "composition_name": None,
                    "component_id": component.component_id,
                    "component_name": component.canonical_name,
                    "matched_via": matched_via,
                    "warnings": [],
                }
            )
            continue

        resolution = resolve_composition_reference(
            import_text=name,
            composition_repository=flow._composition_repository,
            alias_repository=flow._alias_repository,
        )
        composition = None
        matched_via = "created"
        item_warnings: list[str] = []
        if resolution.kind == "composition" and resolution.composition_id:
            composition = flow._composition_repository.get(resolution.composition_id)
            if composition is not None:
                matched_via = str(resolution.matched_via or "existing")
                reused_composition_count += 1

        if composition is None:
            composition = flow.create_composition_with_generated_id(
                composition_name=name,
                library_group=None,
                seed_components=False,
            )
            created_composition_count += 1
            if source_text and sanitize_builder_import_text(source_text) != name:
                alias_warning = flow.create_manual_alias_for_composition(
                    composition_id=composition.composition_id,
                    source_text=source_text,
                )
                if alias_warning:
                    item_warnings.append(alias_warning)

            raw_components = raw_item.get("components")
            component_names: list[str] = []
            if isinstance(raw_components, list):
                for comp_item in raw_components:
                    if isinstance(comp_item, dict):
                        value = sanitize_builder_import_text(str(comp_item.get("name") or ""))
                    else:
                        value = sanitize_builder_import_text(str(comp_item or ""))
                    if value:
                        component_names.append(value)

            if not component_names:
                component_names = suggest_components_from_import_dish_name(name)

            attached_ids: set[str] = set()
            for component_name in component_names:
                component = flow.create_standalone_component(component_name)
                if component.component_id in attached_ids:
                    continue
                attached_ids.add(component.component_id)

                if component.component_id in known_component_ids:
                    reused_component_count += 1
                else:
                    created_component_count += 1
                    known_component_ids.add(component.component_id)

                composition = flow.attach_existing_component_to_composition(
                    composition_id=composition.composition_id,
                    component_id=component.component_id,
                    role="component",
                )

        row_results.append(
            {
                "raw_text": source_text or name,
                "kind": "composition",
                "composition_id": composition.composition_id,
                "composition_name": composition.composition_name,
                "matched_via": matched_via,
                "warnings": item_warnings,
            }
        )
        warnings.extend(item_warnings)

    return {
        "imported_count": imported_count,
        "published_count": imported_count,
        "ignored_count": ignored_count,
        "created_count": created_composition_count,
        "reused_count": reused_composition_count,
        "created_composition_count": created_composition_count,
        "reused_composition_count": reused_composition_count,
        "created_component_count": created_component_count,
        "reused_component_count": reused_component_count,
        "row_results": row_results,
        "warnings": warnings,
    }


def _builder_db_path() -> str:
    return str(current_app.config.get("BUILDER_DB_PATH") or "").strip()


def _session_store() -> dict[str, Any]:
    store = current_app.extensions.get("builder_import_sessions_store")
    if isinstance(store, dict):
        return store
    created = {"sessions": {}, "items": {}}
    current_app.extensions["builder_import_sessions_store"] = created
    return created


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _summarize_session_items(items: list[dict[str, Any]]) -> dict[str, int]:
    detected_dishes = 0
    detected_components = 0
    ignored_rows = 0
    pending_review_count = 0
    published_count = 0

    for item in items:
        item_type = str(item.get("item_type") or "ignore").strip().lower()
        item_status = str(item.get("item_status") or "draft").strip().lower()
        if item_type == "dish":
            detected_dishes += 1
        elif item_type == "component":
            detected_components += 1
        else:
            ignored_rows += 1

        if item_status == "published":
            published_count += 1
        elif item_type != "ignore":
            pending_review_count += 1

    return {
        "total_rows": len(items),
        "detected_dishes": detected_dishes,
        "detected_components": detected_components,
        "ignored_rows": ignored_rows,
        "pending_review_count": pending_review_count,
        "published_count": published_count,
    }


def _derive_session_status(summary: dict[str, int]) -> str:
    pending = int(summary.get("pending_review_count") or 0)
    published = int(summary.get("published_count") or 0)
    actionable = int(summary.get("detected_dishes") or 0) + int(summary.get("detected_components") or 0)
    if pending <= 0 and actionable > 0:
        return "published"
    if published > 0:
        return "partially_published"
    return "draft"


def _normalize_session_item(item: dict[str, Any], index: int, import_type: str) -> dict[str, Any]:
    raw_text = str(item.get("raw_text") or item.get("name") or "").strip()
    cleaned = sanitize_builder_import_text(str(item.get("name") or raw_text))
    classification = str(item.get("classification") or "importable_dish")
    reason = item.get("reason")
    selected = bool(item.get("selected", True))
    hints = item.get("hints") if isinstance(item.get("hints"), list) else []

    item_type = str(item.get("item_type") or "").strip().lower()
    if item_type not in {"component", "dish", "ignore"}:
        if classification != "importable_dish" or not cleaned:
            item_type = "ignore"
        elif import_type == "component_list":
            item_type = "component"
        else:
            item_type = "dish"

    raw_components = item.get("components")
    components: list[str] = []
    if isinstance(raw_components, list):
        for entry in raw_components:
            if isinstance(entry, dict):
                value = sanitize_builder_import_text(str(entry.get("name") or ""))
            else:
                value = sanitize_builder_import_text(str(entry or ""))
            if value:
                components.append(value)

    if item_type == "dish" and not components:
        components = suggest_components_from_import_dish_name(cleaned)

    try:
        item_order = int(item.get("item_order") if item.get("item_order") is not None else index)
    except Exception:
        item_order = index

    if item_type == "ignore":
        selected = False

    category_hint = suggest_component_category(cleaned)
    return {
        "item_id": str(item.get("item_id") or ""),
        "item_order": item_order,
        "raw_text": raw_text,
        "cleaned_name": cleaned,
        "item_type": item_type,
        "selected": selected,
        "item_status": str(item.get("item_status") or "draft"),
        "classification": classification,
        "reason": reason,
        "components": components,
        "category_hint": category_hint,
        "hints": hints,
        "created_at": str(item.get("created_at") or _utc_now()),
        "updated_at": _utc_now(),
    }


def _session_from_drafts(*, draft_items: list[dict[str, Any]], import_type: str, source_name: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session_id = f"imp_{uuid.uuid4().hex[:10]}"
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(draft_items):
        try:
            if not isinstance(item, dict):
                continue
            normalized_items.append(_normalize_session_item(item, index, import_type))
        except Exception:
            continue

    summary = _summarize_session_items(normalized_items)
    status = _derive_session_status(summary)
    now = _utc_now()
    session = {
        "session_id": session_id,
        "source_name": str(source_name or "").strip() or f"Import {now[:19].replace('T', ' ')}",
        "import_type": str(import_type or "menu"),
        "status": status,
        **summary,
        "created_at": now,
        "updated_at": now,
    }
    for index, item in enumerate(normalized_items):
        item["session_id"] = session_id
        # Keep session item IDs unique across repeated imports even when callers reuse temp IDs.
        item["item_id"] = f"{session_id}_item_{index}_{uuid.uuid4().hex[:8]}"
    return session, normalized_items


def _persist_import_session(session: dict[str, Any], items: list[dict[str, Any]]) -> None:
    db_path = _builder_db_path()
    if db_path:
        sqlite_path = initialize_builder_sqlite(db_path)
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO builder_import_sessions (
                    session_id, source_name, import_type, status,
                    total_rows, detected_dishes, detected_components, ignored_rows,
                    pending_review_count, published_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["session_id"],
                    session["source_name"],
                    session["import_type"],
                    session["status"],
                    int(session["total_rows"]),
                    int(session["detected_dishes"]),
                    int(session["detected_components"]),
                    int(session["ignored_rows"]),
                    int(session["pending_review_count"]),
                    int(session["published_count"]),
                    session["created_at"],
                    session["updated_at"],
                ),
            )
            for item in items:
                conn.execute(
                    """
                    INSERT INTO builder_import_session_items (
                        item_id, session_id, item_order, raw_text, cleaned_name,
                        item_type, selected, item_status, classification, reason,
                        components_json, category_hint, hints_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["item_id"],
                        session["session_id"],
                        int(item["item_order"]),
                        item["raw_text"],
                        item["cleaned_name"],
                        item["item_type"],
                        1 if item["selected"] else 0,
                        item["item_status"],
                        item["classification"],
                        item["reason"],
                        json.dumps(item["components"]),
                        item["category_hint"],
                        json.dumps(item["hints"]),
                        item["created_at"],
                        item["updated_at"],
                    ),
                )
        return

    store = _session_store()
    store["sessions"][session["session_id"]] = dict(session)
    store["items"][session["session_id"]] = [dict(item) for item in items]


def _list_import_sessions() -> list[dict[str, Any]]:
    db_path = _builder_db_path()
    if db_path:
        sqlite_path = initialize_builder_sqlite(db_path)
        with sqlite3.connect(sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM builder_import_sessions ORDER BY created_at DESC, session_id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    store = _session_store()
    sessions = list(store["sessions"].values())
    return sorted(sessions, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _load_import_session(session_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    session_id_value = str(session_id or "").strip()
    if not session_id_value:
        return None, []

    db_path = _builder_db_path()
    if db_path:
        sqlite_path = initialize_builder_sqlite(db_path)
        with sqlite3.connect(sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            session_row = conn.execute(
                "SELECT * FROM builder_import_sessions WHERE session_id = ?",
                (session_id_value,),
            ).fetchone()
            if session_row is None:
                return None, []
            item_rows = conn.execute(
                "SELECT * FROM builder_import_session_items WHERE session_id = ? ORDER BY item_order, item_id",
                (session_id_value,),
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in item_rows:
            row_dict = dict(row)
            row_dict["selected"] = bool(int(row_dict.get("selected") or 0))
            row_dict["components"] = list(json.loads(str(row_dict.get("components_json") or "[]")))
            row_dict["hints"] = list(json.loads(str(row_dict.get("hints_json") or "[]")))
            items.append(row_dict)
        return dict(session_row), items

    store = _session_store()
    session = store["sessions"].get(session_id_value)
    items = store["items"].get(session_id_value, [])
    return (dict(session) if isinstance(session, dict) else None), [dict(item) for item in items]


def _save_import_session_item(session_id: str, item: dict[str, Any]) -> None:
    session_id_value = str(session_id or "").strip()
    item_id = str(item.get("item_id") or "").strip()
    if not session_id_value or not item_id:
        return

    db_path = _builder_db_path()
    if db_path:
        sqlite_path = initialize_builder_sqlite(db_path)
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute(
                """
                UPDATE builder_import_session_items
                SET cleaned_name = ?,
                    item_type = ?,
                    selected = ?,
                    item_status = ?,
                    components_json = ?,
                    category_hint = ?,
                    hints_json = ?,
                    updated_at = ?
                WHERE session_id = ? AND item_id = ?
                """,
                (
                    item.get("cleaned_name"),
                    item.get("item_type"),
                    1 if item.get("selected") else 0,
                    item.get("item_status"),
                    json.dumps(item.get("components") or []),
                    item.get("category_hint"),
                    json.dumps(item.get("hints") or []),
                    _utc_now(),
                    session_id_value,
                    item_id,
                ),
            )
        return

    store = _session_store()
    items = store["items"].get(session_id_value, [])
    for index, existing in enumerate(items):
        if str(existing.get("item_id") or "") == item_id:
            items[index] = dict(item)
            break


def _refresh_session_summary(session_id: str) -> dict[str, Any] | None:
    session, items = _load_import_session(session_id)
    if session is None:
        return None
    summary = _summarize_session_items(items)
    session.update(summary)
    session["status"] = _derive_session_status(summary)
    session["updated_at"] = _utc_now()

    db_path = _builder_db_path()
    if db_path:
        sqlite_path = initialize_builder_sqlite(db_path)
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute(
                """
                UPDATE builder_import_sessions
                SET status = ?,
                    total_rows = ?,
                    detected_dishes = ?,
                    detected_components = ?,
                    ignored_rows = ?,
                    pending_review_count = ?,
                    published_count = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    session["status"],
                    int(session["total_rows"]),
                    int(session["detected_dishes"]),
                    int(session["detected_components"]),
                    int(session["ignored_rows"]),
                    int(session["pending_review_count"]),
                    int(session["published_count"]),
                    session["updated_at"],
                    session["session_id"],
                ),
            )
    else:
        store = _session_store()
        store["sessions"][session_id] = dict(session)

    return session


def _is_dev_reset_allowed() -> bool:
    explicit = current_app.config.get("ENABLE_BUILDER_DEV_RESET")
    if explicit is not None:
        return bool(explicit)

    env = str(current_app.config.get("ENV") or "").strip().lower()
    return bool(
        current_app.config.get("TESTING")
        or current_app.config.get("DEBUG")
        or env in {"dev", "development", "local"}
    )


def _reset_builder_state() -> dict[str, Any]:
    builder_db_path = str(current_app.config.get("BUILDER_DB_PATH") or "").strip()
    mode = "sqlite" if builder_db_path else "in_memory"
    before_counts: dict[str, int] = {}

    if builder_db_path:
        db_path = initialize_builder_sqlite(builder_db_path)
        before_counts = clear_builder_sqlite_data(db_path)
    else:
        flow = current_app.extensions.get("builder_flow")
        if not isinstance(flow, BuilderFlow):
            flow = _get_builder_flow()

        from .builder_menu_context_api import _get_menu_context_flow

        menu_flow = current_app.extensions.get("builder_menu_context_flow")
        if not isinstance(menu_flow, BuilderMenuContextFlow):
            menu_flow = _get_menu_context_flow()

        compositions = flow.list_library_compositions()
        menus = menu_flow.list_menus()
        before_counts = {
            "builder_components": len(flow.list_library_components()),
            "builder_component_aliases": len(flow._component_alias_repository.list_all()),
            "builder_compositions": len(compositions),
            "builder_composition_aliases": len(flow._alias_repository.list_all()),
            "builder_composition_components": sum(len(item.components) for item in compositions),
            "builder_menus": len(menus),
            "builder_menu_rows": sum(len(menu_flow.list_menu_rows(menu.menu_id)) for menu in menus),
            "builder_import_sessions": len(_session_store().get("sessions", {})),
            "builder_import_session_items": sum(
                len(items)
                for items in _session_store().get("items", {}).values()
                if isinstance(items, list)
            ),
        }

    for extension_key in [
        "builder_flow",
        "builder_menu_context_flow",
        "builder_menu_service",
        "builder_menu_recipe_repository",
        "builder_menu_ingredient_repository",
        "builder_import_sessions_store",
    ]:
        current_app.extensions.pop(extension_key, None)

    _get_builder_flow()
    from .builder_menu_context_api import _get_menu_context_flow

    _get_menu_context_flow()

    return {"mode": mode, "cleared_counts": before_counts}


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


@bp.delete("/compositions/<composition_id>")
@require_roles("editor", "admin", "superuser")
def delete_composition(composition_id: str):
    composition_id_value = str(composition_id or "").strip()
    if not composition_id_value:
        return _bad_request("composition_id is required")

    try:
        flow = _get_builder_flow()
        composition = flow._composition_service.get_composition(composition_id_value)
        if composition is None:
            return _bad_request(f"composition not found: {composition_id_value}")

        menu_refs: list[str] = []
        from .builder_menu_context_api import _get_menu_context_flow

        menu_flow = _get_menu_context_flow()
        for menu in menu_flow.list_menus():
            rows = menu_flow.list_menu_rows(menu.menu_id)
            if any(str(row.get("composition_id") or "") == composition_id_value for row in rows):
                menu_refs.append(menu.menu_id)

        if menu_refs:
            return _conflict(
                "Dish is used by menu rows and cannot be removed.",
                references={"menu_ids": menu_refs},
            )

        flow._alias_repository.delete_for_composition(composition_id_value)
        flow._composition_service.delete_composition(composition_id_value)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "composition_id": composition_id_value})


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


@bp.delete("/components/<component_id>")
@require_roles("editor", "admin", "superuser")
def delete_component(component_id: str):
    component_id_value = str(component_id or "").strip()
    if not component_id_value:
        return _bad_request("component_id is required")

    try:
        flow = _get_builder_flow()
        component = flow._component_service.get_component(component_id_value)
        if component is None:
            return _bad_request(f"component not found: {component_id_value}")

        referenced_by = []
        for composition in flow.list_library_compositions():
            if any(item.component_id == component_id_value for item in composition.components):
                referenced_by.append(composition.composition_id)

        recipes = flow._recipe_service.list_recipes_for_component(component_id_value)
        if referenced_by or recipes:
            return _conflict(
                "Component is in use and cannot be removed.",
                references={
                    "composition_ids": referenced_by,
                    "recipe_count": len(recipes),
                },
            )

        flow._component_alias_repository.delete_for_component(component_id_value)
        flow._component_service.delete_component(component_id_value)
    except ValueError as exc:
        return _bad_request(str(exc))

    return jsonify({"ok": True, "component_id": component_id_value})


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


@bp.post("/import/sessions")
@require_roles("editor", "admin", "superuser")
def create_import_session():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    import_type = str(payload.get("import_type") or "menu").strip() or "menu"
    source_name = _optional_str(payload, "source_name")

    draft_items: list[dict[str, Any]] = []
    raw_items = payload.get("items")
    if raw_items is not None and not isinstance(raw_items, list):
        return jsonify({
            "ok": False,
            "error": "bad_request",
            "message": "items must be a list",
            "details": {"field": "items", "expected": "list"},
        }), 400

    if isinstance(raw_items, list):
        draft_items = [item for item in raw_items if isinstance(item, dict)]
    else:
        lines: list[str] = []
        raw_text = payload.get("text")
        if raw_text is not None:
            lines.extend(str(raw_text).splitlines())
        raw_lines = payload.get("lines")
        if raw_lines is not None:
            if not isinstance(raw_lines, list):
                return jsonify({
                    "ok": False,
                    "error": "bad_request",
                    "message": "lines must be a list",
                    "details": {"field": "lines", "expected": "list"},
                }), 400
            lines.extend(str(item or "") for item in raw_lines)

        if not lines:
            return jsonify({
                "ok": False,
                "error": "bad_request",
                "message": "lines or items are required",
                "details": {"fields": ["items", "lines", "text"]},
            }), 400
        try:
            draft_items = _build_import_review_drafts(lines)
        except ValueError as exc:
            return jsonify({
                "ok": False,
                "error": "bad_request",
                "message": "unable to parse import lines",
                "details": str(exc),
            }), 400

    try:
        session, items = _session_from_drafts(
            draft_items=draft_items,
            import_type=import_type,
            source_name=source_name,
        )
        _persist_import_session(session, items)
    except (ValueError, sqlite3.IntegrityError) as exc:
        return jsonify({
            "ok": False,
            "error": "bad_request",
            "message": "could not create import session",
            "details": str(exc),
        }), 400

    return jsonify({"ok": True, "session": session, "items": items}), 201


@bp.get("/import/sessions")
@require_roles("editor", "admin", "superuser")
def list_import_sessions():
    sessions = _list_import_sessions()
    pending_count = sum(int(item.get("pending_review_count") or 0) for item in sessions)
    return jsonify({"ok": True, "count": len(sessions), "pending_count": pending_count, "sessions": sessions})


@bp.get("/import/sessions/<session_id>")
@require_roles("editor", "admin", "superuser")
def get_import_session(session_id: str):
    session, items = _load_import_session(session_id)
    if session is None:
        return _bad_request(f"import session not found: {session_id}")

    grouped = {
        "dishes": [item for item in items if str(item.get("item_type") or "") == "dish"],
        "components": [item for item in items if str(item.get("item_type") or "") == "component"],
        "ignored": [item for item in items if str(item.get("item_type") or "") == "ignore"],
        "needs_review": [
            item
            for item in items
            if str(item.get("item_type") or "") != "ignore"
            and str(item.get("item_status") or "draft") != "published"
        ],
    }
    return jsonify({"ok": True, "session": session, "items": items, "grouped": grouped})


@bp.patch("/import/sessions/<session_id>/items/<item_id>")
@require_roles("editor", "admin", "superuser")
def update_import_session_item(session_id: str, item_id: str):
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    session, items = _load_import_session(session_id)
    if session is None:
        return _bad_request(f"import session not found: {session_id}")

    current = next((item for item in items if str(item.get("item_id") or "") == str(item_id)), None)
    if current is None:
        return _bad_request(f"import session item not found: {item_id}")

    updated = dict(current)
    if "selected" in payload:
        updated["selected"] = bool(payload.get("selected"))
    if "item_type" in payload:
        item_type_value = str(payload.get("item_type") or "").strip().lower()
        if item_type_value not in {"component", "dish", "ignore"}:
            return _bad_request("item_type must be component, dish, or ignore")
        updated["item_type"] = item_type_value
    if "name" in payload:
        updated["cleaned_name"] = sanitize_builder_import_text(str(payload.get("name") or ""))
    if "components" in payload:
        raw_components = payload.get("components")
        if not isinstance(raw_components, list):
            return _bad_request("components must be a list")
        component_values: list[str] = []
        for entry in raw_components:
            if isinstance(entry, dict):
                value = sanitize_builder_import_text(str(entry.get("name") or ""))
            else:
                value = sanitize_builder_import_text(str(entry or ""))
            if value:
                component_values.append(value)
        updated["components"] = component_values

    updated["category_hint"] = suggest_component_category(updated.get("cleaned_name") or "")
    updated["updated_at"] = _utc_now()
    _save_import_session_item(session_id, updated)
    refreshed = _refresh_session_summary(session_id)
    return jsonify({"ok": True, "session": refreshed, "item": updated})


@bp.post("/import/sessions/<session_id>/ignore-selected")
@require_roles("editor", "admin", "superuser")
def ignore_import_session_selected(session_id: str):
    session, items = _load_import_session(session_id)
    if session is None:
        return _bad_request(f"import session not found: {session_id}")

    ignored = 0
    for item in items:
        if not bool(item.get("selected")):
            continue
        item["item_type"] = "ignore"
        item["item_status"] = "ignored"
        item["selected"] = False
        item["updated_at"] = _utc_now()
        _save_import_session_item(session_id, item)
        ignored += 1

    refreshed = _refresh_session_summary(session_id)
    return jsonify({"ok": True, "ignored_count": ignored, "session": refreshed})


@bp.post("/import/sessions/<session_id>/publish-selected")
@require_roles("editor", "admin", "superuser")
def publish_import_session_selected(session_id: str):
    session, items = _load_import_session(session_id)
    if session is None:
        return _bad_request(f"import session not found: {session_id}")

    selected_items = [
        {
            "selected": bool(item.get("selected")),
            "item_type": item.get("item_type"),
            "raw_text": item.get("raw_text"),
            "name": item.get("cleaned_name"),
            "components": [{"name": value} for value in list(item.get("components") or [])],
        }
        for item in items
        if bool(item.get("selected")) and str(item.get("item_type") or "") != "ignore"
    ]

    summary = _publish_review_drafts(selected_items)

    published_raw = {
        str(entry.get("raw_text") or "").strip().lower()
        for entry in list(summary.get("row_results") or [])
    }
    for item in items:
        if not bool(item.get("selected")):
            continue
        raw_key = str(item.get("raw_text") or "").strip().lower()
        if raw_key in published_raw:
            item["item_status"] = "published"
            item["selected"] = False
            item["updated_at"] = _utc_now()
            _save_import_session_item(session_id, item)

    refreshed = _refresh_session_summary(session_id)
    return jsonify({"ok": True, "session": refreshed, "summary": summary})


@bp.post("/import/publish-drafts")
@require_roles("editor", "admin", "superuser")
def import_publish_review_drafts():
    payload = _require_json_object()
    if isinstance(payload, tuple):
        return payload

    session_id = _optional_str(payload, "session_id")
    if session_id:
        session, items = _load_import_session(session_id)
        if session is None:
            return _bad_request(f"import session not found: {session_id}")

        selected_items = [
            {
                "selected": bool(item.get("selected")),
                "item_type": item.get("item_type"),
                "raw_text": item.get("raw_text"),
                "name": item.get("cleaned_name"),
                "components": [{"name": value} for value in list(item.get("components") or [])],
            }
            for item in items
            if bool(item.get("selected")) and str(item.get("item_type") or "") != "ignore"
        ]
        summary = _publish_review_drafts(selected_items)

        published_raw = {
            str(entry.get("raw_text") or "").strip().lower()
            for entry in list(summary.get("row_results") or [])
        }
        for item in items:
            if not bool(item.get("selected")):
                continue
            raw_key = str(item.get("raw_text") or "").strip().lower()
            if raw_key in published_raw:
                item["item_status"] = "published"
                item["selected"] = False
                item["updated_at"] = _utc_now()
                _save_import_session_item(session_id, item)

        refreshed = _refresh_session_summary(session_id)
        return jsonify({"ok": True, "session": refreshed, "summary": summary})

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return _bad_request("items must be a list")

    items = [item for item in raw_items if isinstance(item, dict)]
    summary = _publish_review_drafts(items)
    return jsonify({"ok": True, "summary": summary})


@bp.post("/reset")
@require_roles("admin", "superuser")
def reset_builder_dev_data():
    if not _is_dev_reset_allowed():
        return jsonify({"ok": False, "error": "forbidden", "message": "builder reset is dev-only"}), 403

    details = _reset_builder_state()
    return jsonify({"ok": True, **details})


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
    drafts = _build_import_review_drafts(lines)

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
                "draft_items": drafts,
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

    draft_source = [item.raw_text for item in preview.classified_lines]
    drafts = _build_import_review_drafts(draft_source)

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
                "draft_items": drafts,
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
