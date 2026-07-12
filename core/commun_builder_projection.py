from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from flask import current_app, has_app_context

from .commun_builder_linkage import CommunBuilderMenuLinkService
from .builder_sqlite import (
    SQLiteMenuDetailRepository,
    SQLiteMenuRepository,
    initialize_builder_sqlite,
)


_SUPPORTED_BUILDER_MEALS = {
    "lunch": "lunch",
    "dinner": "dinner",
}

_SUPPORTED_EXPLICIT_VARIANTS = {"main", "alt1", "alt2", "alt3", "alt4", "alt5", "dessert"}
_UNRESOLVED_VARIANT = "unresolved_variant"


@dataclass(frozen=True)
class CommunMenuProjectionRow:
    day: str
    meal: str
    variant_type: str
    sort_order: int
    builder_menu_id: str
    builder_menu_version: int
    builder_menu_row_id: str
    composition_id: str | None
    resolved: bool
    text: str
    unresolved_text: str | None
    error: str | None = None


@dataclass(frozen=True)
class CommunMenuWeekProjection:
    tenant_id: int
    site_id: str
    year: int
    week: int
    builder_menu_id: str
    builder_menu_version: int
    builder_status: str
    rows: list[CommunMenuProjectionRow] = field(default_factory=list)
    projection_version: int = 1
    source: str = "commun.builder.projection_shadow_v0"


@dataclass(frozen=True)
class CommunBuilderProjectionComparison:
    status: str
    legacy_row_count: int
    builder_row_count: int
    missing_in_builder: list[dict[str, Any]] = field(default_factory=list)
    missing_in_legacy: list[dict[str, Any]] = field(default_factory=list)
    text_mismatches: list[dict[str, Any]] = field(default_factory=list)
    slot_mismatches: list[dict[str, Any]] = field(default_factory=list)
    order_mismatches: list[dict[str, Any]] = field(default_factory=list)
    version_mismatch: dict[str, Any] | None = None
    difference_count: int = 0
    builder_menu_id: str | None = None
    linked_version: int | None = None
    current_version: int | None = None


@dataclass(frozen=True)
class CommunBuilderProjectionOutcome:
    status: str
    projection: CommunMenuWeekProjection | None = None
    builder_menu_id: str | None = None
    linked_version: int | None = None
    current_version: int | None = None
    error: str | None = None


def _normalize_day(value: str) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "mon": "monday",
        "monday": "monday",
        "tue": "tuesday",
        "tuesday": "tuesday",
        "wed": "wednesday",
        "wednesday": "wednesday",
        "thu": "thursday",
        "thursday": "thursday",
        "fri": "friday",
        "friday": "friday",
        "sat": "saturday",
        "saturday": "saturday",
        "sun": "sunday",
        "sunday": "sunday",
    }
    return aliases.get(raw, raw)


def _normalize_builder_meal_slot(value: str) -> tuple[str, str | None]:
    raw = str(value or "").strip().lower()
    if not raw:
        raise ValueError("meal_slot missing")
    base, _, suffix = raw.partition("_")
    meal = _SUPPORTED_BUILDER_MEALS.get(base)
    if meal is None:
        raise ValueError(f"unknown meal slot: {value}")
    variant = suffix.strip() or None
    if variant and variant not in _SUPPORTED_EXPLICIT_VARIANTS:
        raise ValueError(f"unknown variant slot: {value}")
    return meal, variant


def _normalize_row_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    return (int(row.get("sort_order") or 0), str(row.get("builder_menu_row_id") or ""))


def _projection_text(*, resolved: bool, composition_name: str | None, unresolved_text: str | None) -> str:
    if resolved:
        return str(composition_name or "").strip() if composition_name is not None else ""
    return str(unresolved_text or "").strip() if unresolved_text is not None else ""


def _row_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("day") or ""), str(row.get("meal") or ""), str(row.get("variant_type") or ""))


def _compare_row_groups(
    builder_rows: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    builder_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    legacy_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in builder_rows:
        builder_groups[_row_identity(row)].append(row)
    for row in legacy_rows:
        legacy_groups[_row_identity(row)].append(row)

    missing_in_builder: list[dict[str, Any]] = []
    missing_in_legacy: list[dict[str, Any]] = []
    text_mismatches: list[dict[str, Any]] = []
    order_mismatches: list[dict[str, Any]] = []

    all_keys = sorted(set(builder_groups) | set(legacy_groups))
    for key in all_keys:
        builder_group = sorted(builder_groups.get(key, []), key=_normalize_row_sort_key)
        legacy_group = sorted(legacy_groups.get(key, []), key=_normalize_row_sort_key)
        paired_count = min(len(builder_group), len(legacy_group))

        for index in range(paired_count):
            builder_row = builder_group[index]
            legacy_row = legacy_group[index]
            if builder_row["text"].strip() != legacy_row["text"].strip():
                text_mismatches.append(
                    {
                        "key": key,
                        "index": index,
                        "builder": builder_row["text"],
                        "legacy": legacy_row["text"],
                    }
                )

        if len(builder_group) != len(legacy_group):
            if len(builder_group) > len(legacy_group):
                for row in builder_group[paired_count:]:
                    missing_in_legacy.append({"key": key, "row": row})
            else:
                for row in legacy_group[paired_count:]:
                    missing_in_builder.append({"key": key, "row": row})

        builder_sequence = [row["text"].strip() for row in builder_group]
        legacy_sequence = [row["text"].strip() for row in legacy_group]
        if builder_sequence != legacy_sequence:
            order_mismatches.append(
                {
                    "key": key,
                    "builder_sequence": builder_sequence,
                    "legacy_sequence": legacy_sequence,
                }
            )

    return missing_in_builder, missing_in_legacy, text_mismatches, order_mismatches


def _get_builder_menu_context_flow() -> Any:
    if not has_app_context():
        return None
    flow = current_app.extensions.get("builder_menu_context_flow")
    if flow is not None:
        return flow

    builder_flow = current_app.extensions.get("builder_flow")
    if builder_flow is None:
        try:
            from .builder_api import _get_builder_flow

            builder_flow = _get_builder_flow()
        except Exception:
            builder_flow = None
    if builder_flow is None:
        return None

    menu_service = current_app.extensions.get("builder_menu_service")
    if menu_service is None:
        builder_db_path = str(current_app.config.get("BUILDER_DB_PATH") or "").strip()
        try:
            if builder_db_path:
                from .menu import MenuService

                db_path = initialize_builder_sqlite(builder_db_path)
                menu_service = MenuService(
                    menu_repository=SQLiteMenuRepository(db_path=db_path),
                    menu_detail_repository=SQLiteMenuDetailRepository(db_path=db_path),
                    composition_repository=builder_flow._composition_repository,
                )
            else:
                from .menu import MenuService

                menu_service = MenuService(composition_repository=builder_flow._composition_repository)
        except Exception:
            menu_service = None
        if menu_service is not None:
            current_app.extensions["builder_menu_service"] = menu_service

    if menu_service is None:
        return None

    try:
        from .builder_menu_context_flow import BuilderMenuContextFlow
        from .components import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository
        from .menu import InMemoryCompositionAliasRepository

        flow = BuilderMenuContextFlow(
            menu_service=menu_service,
            composition_repository=builder_flow._composition_repository,
            alias_repository=builder_flow._alias_repository,
            recipe_repository=current_app.extensions.setdefault(
                "builder_menu_recipe_repository", InMemoryRecipeRepository()
            ),
            ingredient_repository=current_app.extensions.setdefault(
                "builder_menu_ingredient_repository", InMemoryRecipeIngredientLineRepository()
            ),
            library_flow=builder_flow,
        )
        current_app.extensions["builder_menu_context_flow"] = flow
        return flow
    except Exception:
        return None


def _get_legacy_weekview_rows(legacy_weekview: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(legacy_weekview.get("rows"), list):
        rows_out: list[dict[str, Any]] = []
        for index, row in enumerate(legacy_weekview.get("rows") or []):
            if not isinstance(row, dict):
                continue
            rows_out.append(
                {
                    "day": _normalize_day(str(row.get("day") or "")),
                    "meal": _normalize_builder_meal_slot(str(row.get("meal") or row.get("meal_slot") or ""))[0],
                    "variant_type": str(row.get("variant_type") or "").strip().lower(),
                    "sort_order": int(row.get("sort_order") or index),
                    "dish_id": row.get("dish_id"),
                    "text": str(row.get("text") or row.get("dish_name") or "").strip(),
                }
            )
        return rows_out

    rows: list[dict[str, Any]] = []
    days = legacy_weekview.get("days") or {}
    for day, meals in days.items():
        for meal, variants in (meals or {}).items():
            for variant_type, info in (variants or {}).items():
                rows.append(
                    {
                        "day": _normalize_day(str(day)),
                        "meal": _normalize_builder_meal_slot(str(meal))[0],
                        "variant_type": str(variant_type or "").strip().lower(),
                        "sort_order": len(rows),
                        "dish_id": info.get("dish_id") if isinstance(info, dict) else None,
                        "text": str(info.get("dish_name") or "").strip() if isinstance(info, dict) else "",
                    }
                )
    return rows


class CommunBuilderMenuProjectionReader:
    def __init__(self, *, linkage_service: CommunBuilderMenuLinkService | None = None) -> None:
        self._linkage_service = linkage_service or CommunBuilderMenuLinkService()

    def get_projection(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
    ) -> CommunBuilderProjectionOutcome:
        link = self._linkage_service.get_link_for_week(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
        )
        if link is None:
            return CommunBuilderProjectionOutcome(status="no_link")

        flow = _get_builder_menu_context_flow()
        if flow is None:
            return CommunBuilderProjectionOutcome(
                status="projection_error",
                builder_menu_id=link.builder_menu_id,
                linked_version=int(link.builder_menu_version),
                error="builder_menu_context_flow_unavailable",
            )

        menus = flow.list_menus()
        menu = next((item for item in menus if str(getattr(item, "menu_id", "")).strip() == link.builder_menu_id), None)
        if menu is None:
            return CommunBuilderProjectionOutcome(
                status="projection_error",
                builder_menu_id=link.builder_menu_id,
                linked_version=int(link.builder_menu_version),
                error="builder_menu_not_found",
            )

        current_version = int(getattr(menu, "version", 0) or 0)
        if current_version != int(link.builder_menu_version):
            return CommunBuilderProjectionOutcome(
                status="version_mismatch",
                builder_menu_id=link.builder_menu_id,
                linked_version=int(link.builder_menu_version),
                current_version=current_version,
                error="version_mismatch",
            )

        rows_raw = flow.list_menu_rows(link.builder_menu_id)
        rows_out: list[CommunMenuProjectionRow] = []
        composition_repository = getattr(flow, "_composition_repository", None)
        row_errors: list[str] = []
        for row in rows_raw:
            # Builder day/meal row order is not kommun Alt identity.
            # Explicit variant metadata is required for safe mapping.
            day = _normalize_day(str(row.get("day") or ""))
            meal_slot_value = str(row.get("meal_slot") or "")
            meal, explicit_variant = _normalize_builder_meal_slot(meal_slot_value)
            variant_type = explicit_variant or _UNRESOLVED_VARIANT

            composition_id = str(row.get("composition_id") or "").strip() or None
            unresolved_text = str(row.get("unresolved_text") or "").strip() or None
            composition_name = str(row.get("composition_name") or "").strip() or None
            resolved = bool(composition_id)
            error = None
            if explicit_variant is None:
                error = "variant_mapping_missing"
            if resolved and composition_repository is not None:
                composition = composition_repository.get(composition_id)
                if composition is None:
                    resolved = False
                    error = "composition_missing"
                    composition_id = None
                    composition_name = None
            if not resolved and unresolved_text is None and error is None:
                error = "unresolved_text_missing"

            text_value = _projection_text(
                resolved=resolved,
                composition_name=composition_name,
                unresolved_text=unresolved_text,
            )
            rows_out.append(
                CommunMenuProjectionRow(
                    day=day,
                    meal=meal,
                    variant_type=variant_type,
                    sort_order=int(row.get("sort_order") or 0),
                    builder_menu_id=link.builder_menu_id,
                    builder_menu_version=int(link.builder_menu_version),
                    builder_menu_row_id=str(row.get("menu_detail_id") or ""),
                    composition_id=composition_id,
                    resolved=resolved,
                    text=text_value,
                    unresolved_text=unresolved_text if not resolved else None,
                    error=error,
                )
            )
            if error:
                row_errors.append(error)

        projection = CommunMenuWeekProjection(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
            builder_menu_id=link.builder_menu_id,
            builder_menu_version=int(link.builder_menu_version),
            builder_status=str(getattr(menu, "status", "") or "draft").strip() or "draft",
            rows=rows_out,
        )
        return CommunBuilderProjectionOutcome(
            status="projection_error" if row_errors else "ok",
            projection=projection,
            builder_menu_id=link.builder_menu_id,
            linked_version=int(link.builder_menu_version),
            current_version=current_version,
            error=row_errors[0] if row_errors else None,
        )

    def compare_with_legacy(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_weekview: dict[str, Any],
    ) -> CommunBuilderProjectionComparison:
        outcome = self.get_projection(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
        if outcome.status == "no_link":
            return CommunBuilderProjectionComparison(
                status="no_link",
                legacy_row_count=len(_get_legacy_weekview_rows(legacy_weekview)),
                builder_row_count=0,
                builder_menu_id=None,
            )
        if outcome.status == "version_mismatch":
            return CommunBuilderProjectionComparison(
                status="version_mismatch",
                legacy_row_count=len(_get_legacy_weekview_rows(legacy_weekview)),
                builder_row_count=0,
                builder_menu_id=outcome.builder_menu_id,
                linked_version=outcome.linked_version,
                current_version=outcome.current_version,
                version_mismatch={
                    "linked_version": outcome.linked_version,
                    "current_version": outcome.current_version,
                },
            )
        if outcome.status != "ok" or outcome.projection is None:
            return CommunBuilderProjectionComparison(
                status="projection_error",
                legacy_row_count=len(_get_legacy_weekview_rows(legacy_weekview)),
                builder_row_count=0,
                builder_menu_id=outcome.builder_menu_id,
                linked_version=outcome.linked_version,
                current_version=outcome.current_version,
                version_mismatch={"error": outcome.error} if outcome.error else None,
            )

        builder_rows = [
            {
                "day": row.day,
                "meal": row.meal,
                "variant_type": row.variant_type,
                "sort_order": row.sort_order,
                "text": row.text.strip(),
                "resolved": row.resolved,
                "builder_menu_row_id": row.builder_menu_row_id,
            }
            for row in outcome.projection.rows
        ]
        legacy_rows = _get_legacy_weekview_rows(legacy_weekview)

        (
            missing_in_builder,
            missing_in_legacy,
            text_mismatches,
            order_mismatches,
        ) = _compare_row_groups(builder_rows, legacy_rows)

        difference_count = len(missing_in_builder) + len(missing_in_legacy) + len(text_mismatches) + len(order_mismatches)
        comparison_status = "match" if difference_count == 0 else "difference"
        return CommunBuilderProjectionComparison(
            status=comparison_status,
            legacy_row_count=len(legacy_rows),
            builder_row_count=len(builder_rows),
            missing_in_builder=missing_in_builder,
            missing_in_legacy=missing_in_legacy,
            text_mismatches=text_mismatches,
            slot_mismatches=[],
            order_mismatches=order_mismatches,
            difference_count=difference_count,
            builder_menu_id=outcome.builder_menu_id,
            linked_version=outcome.linked_version,
            current_version=outcome.current_version,
        )


def get_shadow_projection_reader() -> CommunBuilderMenuProjectionReader:
    if not has_app_context():
        return CommunBuilderMenuProjectionReader()
    reader = current_app.extensions.get("commun_builder_projection_reader")
    if isinstance(reader, CommunBuilderMenuProjectionReader):
        return reader
    reader = CommunBuilderMenuProjectionReader()
    current_app.extensions["commun_builder_projection_reader"] = reader
    return reader