from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging

from .builder import BuilderFlow
from .builder.library_scope import ActorContext, ObjectScope
from .builder.declaration_readiness import (
    ComponentDeclarationReadiness,
    MenuDeclarationReadiness,
    MenuRowDeclarationReadiness,
)
from .builder.diet_conflict_preview import DietConflictPreview, merge_diet_conflict_previews
from .builder_sqlite import builder_transaction
from .components import (
    Composition,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from .menu import (
    ImportedMenuRow,
    InMemoryCompositionAliasRepository,
    MenuDetail,
    MenuDetailCostBreakdown,
    MenuImportSummary,
    MenuService,
    calculate_menu_detail_cost,
    import_menu_rows,
)
from .planera_v2.adapters import build_menu_composition_payload
from .planera_v2.adapters import build_menu_composition_grouped_payload
from .planera_v2.adapters import build_menu_composition_production_shape_payload

logger = logging.getLogger(__name__)


_MISSING = object()


class ReviewedCompositionConflict(ValueError):
    """Raised when a reviewed creation retry conflicts with persisted state."""


@dataclass(frozen=True)
class MenuCostOverview:
    menu_id: str
    detail_costs: list[MenuDetailCostBreakdown] = field(default_factory=list)
    unresolved_count: int = 0
    warnings: list[str] = field(default_factory=list)


class BuilderMenuContextFlow:
    def __init__(
        self,
        *,
        menu_service: MenuService,
        composition_repository: InMemoryCompositionRepository,
        alias_repository: InMemoryCompositionAliasRepository,
        recipe_repository: InMemoryRecipeRepository,
        ingredient_repository: InMemoryRecipeIngredientLineRepository,
        library_flow: BuilderFlow,
    ) -> None:
        self._menu_service = menu_service
        self._composition_repository = composition_repository
        self._alias_repository = alias_repository
        self._recipe_repository = recipe_repository
        self._ingredient_repository = ingredient_repository
        self._library_flow = library_flow

    def create_menu(
        self,
        menu_id: str,
        site_id: str,
        week_key: str,
        *,
        title: str | None = None,
        version: int = 1,
        status: str = "draft",
    ):
        return self._menu_service.create_menu(
            menu_id=menu_id,
            title=title,
            site_id=site_id,
            week_key=week_key,
            version=version,
            status=status,
        )

    def list_menus(self):
        return self._menu_service.list_menus()

    def get_menu_composition_adapter_payload(
        self,
        menu_id: str,
        *,
        menu_detail_id: str | None = None,
    ) -> dict[str, object]:
        menu = self._menu_service.get_menu(str(menu_id))
        if menu is None:
            raise ValueError(f"menu not found: {menu_id}")

        details = self._menu_service.list_menu_details(str(menu_id))
        if menu_detail_id:
            target_detail_id = str(menu_detail_id).strip()
            if not target_detail_id:
                raise ValueError("menu_detail_id must be non-empty")
            if not any(detail.menu_detail_id == target_detail_id for detail in details):
                raise ValueError("menu_detail_id not found for menu")

        payload = build_menu_composition_payload(
            menu=menu,
            menu_details=details,
            composition_repository=self._composition_repository,
            menu_detail_id=menu_detail_id,
        )
        return payload

    def get_menu_composition_grouped_adapter_payload(
        self,
        menu_id: str,
    ) -> dict[str, object]:
        menu = self._menu_service.get_menu(str(menu_id))
        if menu is None:
            raise ValueError(f"menu not found: {menu_id}")

        details = self._menu_service.list_menu_details(str(menu_id))
        payload = build_menu_composition_grouped_payload(
            menu=menu,
            menu_details=details,
            composition_repository=self._composition_repository,
        )
        return payload

    def get_menu_composition_production_shape_adapter_payload(
        self,
        menu_id: str,
    ) -> dict[str, object]:
        menu = self._menu_service.get_menu(str(menu_id))
        if menu is None:
            raise ValueError(f"menu not found: {menu_id}")

        details = self._menu_service.list_menu_details(str(menu_id))
        payload = build_menu_composition_production_shape_payload(
            menu=menu,
            menu_details=details,
            composition_repository=self._composition_repository,
        )
        return payload

    def add_composition_menu_row(
        self,
        *,
        menu_id: str,
        day: str,
        meal_slot: str,
        composition_id: str,
        note: str | None = None,
        sort_order: int = 0,
        menu_detail_id: str | None = None,
        display_label: str | None = None,
        selection_group_id: str | None = None,
    ) -> MenuDetail:
        detail_id = str(menu_detail_id or "").strip()
        if not detail_id:
            existing = self._menu_service.list_menu_details(menu_id)
            detail_id = f"{menu_id}-row-{len(existing) + 1}"
        return self._menu_service.add_menu_detail(
            menu_detail_id=detail_id,
            menu_id=menu_id,
            day=day,
            meal_slot=meal_slot,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text=None,
            note=note,
            sort_order=sort_order,
            display_label=display_label or meal_slot,
            row_kind="legacy",
            selection_group_id=selection_group_id,
        )

    def create_empty_menu_row(
        self,
        *,
        menu_id: str,
        day: str,
        display_label: str,
        note: str | None = None,
        sort_order: int | None = None,
        menu_detail_id: str | None = None,
        selection_group_id: str | None = None,
    ) -> MenuDetail:
        detail_id = str(menu_detail_id or "").strip()
        existing = self._menu_service.list_menu_details(menu_id)
        if not detail_id:
            detail_id = f"{menu_id}-row-{len(existing) + 1}"
        resolved_sort_order = int(sort_order) if sort_order is not None else (
            (max((int(detail.sort_order) for detail in existing), default=0)) + 10
        )
        return self._menu_service.create_empty_menu_detail(
            menu_detail_id=detail_id,
            menu_id=menu_id,
            day=day,
            display_label=display_label,
            note=note,
            sort_order=resolved_sort_order,
            selection_group_id=selection_group_id,
        )

    def update_composition_menu_row(
        self,
        *,
        menu_id: str,
        menu_detail_id: str,
        day: str,
        meal_slot: str,
        composition_id: str,
        note: str | None = None,
        sort_order: int | None = None,
        selection_group_id: object = _MISSING,
    ) -> MenuDetail:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")

        update_kwargs = dict(
            menu_detail_id=menu_detail_id,
            day=day,
            meal_slot=meal_slot,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text="",
            note=note,
            sort_order=sort_order,
        )
        if selection_group_id is not _MISSING:
            update_kwargs["selection_group_id"] = selection_group_id
        return self._menu_service.update_menu_detail(**update_kwargs)

    def clear_menu_row_composition(
        self,
        *,
        menu_id: str,
        menu_detail_id: str,
    ) -> MenuDetail:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")

        return self._menu_service.clear_menu_detail(menu_detail_id=menu_detail_id)

    def delete_menu_row(self, *, menu_id: str, menu_detail_id: str) -> None:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")
        self._menu_service.remove_menu_detail(menu_detail_id)

    def list_menu_rows(self, menu_id: str) -> list[dict[str, str | int | None]]:
        rows: list[dict[str, str | int | None]] = []
        for insertion_index, detail in enumerate(self._menu_service.list_menu_details(menu_id)):
            composition_name: str | None = None
            if detail.composition_id:
                composition = self._composition_repository.get(detail.composition_id)
                if composition is not None:
                    composition_name = composition.composition_name
            rows.append(
                {
                    "menu_detail_id": detail.menu_detail_id,
                    "menu_id": detail.menu_id,
                    "day": detail.day,
                    "meal_slot": detail.meal_slot,
                    "display_label": detail.display_label,
                    "row_kind": detail.row_kind,
                    "composition_ref_type": detail.composition_ref_type,
                    "is_empty": detail.composition_ref_type == "empty",
                    "composition_id": detail.composition_id,
                    "composition_name": composition_name,
                    "unresolved_text": detail.unresolved_text,
                    "note": detail.note,
                    "sort_order": detail.sort_order,
                    "selection_group_id": detail.selection_group_id,
                    "_insertion_index": insertion_index,
                }
            )

        ordered_rows = sorted(
            rows,
            key=lambda row: (
                int(row.get("sort_order") or 0),
                int(row.get("_insertion_index") or 0),
                str(row.get("menu_detail_id") or ""),
            ),
        )

        cleaned_rows: list[dict[str, str | int | None]] = []
        for row in ordered_rows:
            cleaned = dict(row)
            cleaned.pop("_insertion_index", None)
            cleaned_rows.append(cleaned)
        return cleaned_rows

    def list_menu_rows_grouped(
        self,
        menu_id: str,
    ) -> list[dict[str, str | int | list[dict[str, str | int | None]]]]:
        rows = self.list_menu_rows(menu_id)
        grouped: dict[tuple[str, str], dict[str, object]] = {}
        group_order: list[tuple[str, str]] = []

        for row in rows:
            day = str(row.get("day") or "")
            meal_slot = str(row.get("meal_slot") or "")
            key = (day, meal_slot)
            if key not in grouped:
                grouped[key] = {
                    "rows": [],
                    "first_insertion_index": len(group_order),
                }
                group_order.append(key)
            grouped[key]["rows"].append(row)

        groups: list[dict[str, str | int | list[dict[str, str | int | None]]]] = []
        for day, meal_slot in group_order:
            grouped_rows = grouped[(day, meal_slot)]["rows"]
            groups.append(
                {
                    "day": day,
                    "meal_slot": meal_slot,
                    "count": len(grouped_rows),
                    "rows": grouped_rows,
                    "_first_sort_order": min(
                        int((row.get("sort_order") or 0)) for row in grouped_rows
                    ),
                    "_first_insertion_index": int(
                        grouped[(day, meal_slot)]["first_insertion_index"] or 0
                    ),
                }
            )

        ordered_groups = sorted(
            groups,
            key=lambda group: (
                int(group.get("_first_sort_order") or 0),
                int(group.get("_first_insertion_index") or 0),
                str(group.get("day") or ""),
                str(group.get("meal_slot") or ""),
            ),
        )

        cleaned_groups: list[dict[str, str | int | list[dict[str, str | int | None]]]] = []
        for group in ordered_groups:
            cleaned = dict(group)
            cleaned.pop("_first_sort_order", None)
            cleaned.pop("_first_insertion_index", None)
            cleaned_groups.append(cleaned)
        return cleaned_groups

    def get_menu_declaration_readiness(
        self,
        menu_id: str,
    ) -> MenuDeclarationReadiness:
        menu = self._menu_service.get_menu(str(menu_id))
        if menu is None:
            raise ValueError(f"menu not found: {menu_id}")

        rows = self.list_menu_rows(str(menu_id))
        row_models: list[MenuRowDeclarationReadiness] = []
        warnings: list[str] = []

        for row in rows:
            row_warnings: list[str] = []
            component_models: list[ComponentDeclarationReadiness] = []
            row_signals: tuple[str, ...] = ()
            row_conflict_preview = DietConflictPreview()
            composition_id = str(row.get("composition_id") or "").strip() or None
            composition_ref_type = str(row.get("composition_ref_type") or "")
            composition_name = (
                str(row.get("composition_name") or "").strip() or None
            )

            if composition_ref_type != "composition" or composition_id is None:
                unresolved_text = str(row.get("unresolved_text") or "").strip()
                if unresolved_text:
                    row_warnings.append(f"unresolved menu row text: {unresolved_text}")
            else:
                try:
                    composition_readiness = self._library_flow.preview_composition_declaration_readiness(
                        composition_id=composition_id,
                    )
                    row_signals = tuple(composition_readiness.trait_signals_present)
                    row_conflict_preview = composition_readiness.conflict_preview
                    component_models = list(composition_readiness.components)
                    row_warnings.extend(composition_readiness.warnings)
                except ValueError as exc:
                    row_warnings.append(str(exc))

            model = MenuRowDeclarationReadiness(
                menu_detail_id=str(row.get("menu_detail_id") or ""),
                composition_ref_type=composition_ref_type,
                composition_id=composition_id,
                composition_name=composition_name,
                trait_signals_present=row_signals,
                conflict_preview=row_conflict_preview,
                components=component_models,
                warnings=row_warnings,
            )
            row_models.append(model)
            warnings.extend([f"row {model.menu_detail_id}: {message}" for message in row_warnings])

        signal_union = sorted(
            {
                signal
                for row_model in row_models
                for signal in row_model.trait_signals_present
            }
        )
        merged_conflicts = merge_diet_conflict_previews(
            [row_model.conflict_preview for row_model in row_models]
        )
        return MenuDeclarationReadiness(
            menu_id=menu.menu_id,
            trait_signals_present=tuple(signal_union),
            conflict_preview=merged_conflicts,
            rows=row_models,
            warnings=warnings,
        )

    def import_menu_rows(self, menu_id: str, rows: list[ImportedMenuRow]) -> MenuImportSummary:
        return import_menu_rows(
            menu_id=menu_id,
            rows=rows,
            menu_service=self._menu_service,
            composition_repository=self._composition_repository,
            alias_repository=self._alias_repository,
        )

    def list_unresolved_menu_details(self, menu_id: str) -> list[MenuDetail]:
        details = self._menu_service.list_menu_details(menu_id)
        return [detail for detail in details if detail.composition_ref_type == "unresolved"]

    def resolve_menu_detail(
        self,
        menu_id: str,
        menu_detail_id: str,
        composition_id: str,
        *,
        actor: ActorContext | None = None,
        require_site_scope: bool = False,
    ) -> MenuDetail:
        menu = self._menu_service.get_menu(str(menu_id))
        if menu is None:
            raise ValueError("menu not found")
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")
        if require_site_scope:
            if actor is None or not actor.site_id or str(menu.site_id or "") != str(actor.site_id):
                raise ValueError("menu row is outside the authenticated site")
            if str(menu.status or "").lower() == "published":
                raise ValueError("published menu rows cannot be resolved")
            composition = self._library_flow.get_library_composition(
                str(composition_id),
                actor=actor,
            )
            if composition is None:
                raise ValueError("composition is outside the authenticated site")

        return self._menu_service.update_menu_detail(
            menu_detail_id=menu_detail_id,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text="",
        )

    def create_composition_from_unresolved_row(
        self,
        menu_id: str,
        menu_detail_id: str,
        composition_name: str,
        *,
        actor: ActorContext | None = None,
    ) -> tuple[Composition, MenuDetail, list[str]]:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")
        if match.composition_ref_type != "unresolved":
            raise ValueError("menu detail must be unresolved")
        unresolved_text = str(match.unresolved_text or "").strip()
        if not unresolved_text:
            raise ValueError("unresolved row required")

        composition = self._library_flow.create_composition_with_generated_id(composition_name=composition_name, actor=actor)

        for suggestion in self._library_flow.suggest_components_from_text(unresolved_text):
            composition = self._library_flow.add_component_to_composition(
                composition_id=composition.composition_id,
                component_name=suggestion,
                role="component",
                actor=actor,
            )

        warnings: list[str] = []
        alias_warning = self._library_flow.create_manual_alias_for_composition(
            composition_id=composition.composition_id,
            source_text=unresolved_text,
        )
        if alias_warning:
            warnings.append(alias_warning)
            logger.warning(alias_warning)

        updated = self.resolve_menu_detail(
            menu_id=menu_id,
            menu_detail_id=menu_detail_id,
            composition_id=composition.composition_id,
        )
        return composition, updated, warnings

    def create_reviewed_site_composition_from_unresolved_row(
        self,
        menu_id: str,
        menu_detail_id: str,
        composition_name: str,
        component_selections: list[dict[str, object]],
        *,
        idempotency_key: str,
        actor: ActorContext,
        library_group: str | None = None,
    ) -> tuple[Composition, MenuDetail]:
        if not str(actor.site_id or "").strip():
            raise ValueError("authenticated site is required")
        name_value = str(composition_name or "").strip()
        if not name_value:
            raise ValueError("composition_name is required")
        key_value = str(idempotency_key or "").strip()
        if not key_value:
            raise ValueError("idempotency_key is required")
        if not isinstance(component_selections, list):
            raise ValueError("components must be a list")

        normalized_selections: list[dict[str, str | None]] = []
        for index, selection in enumerate(component_selections):
            if not isinstance(selection, dict):
                raise ValueError(f"components[{index}] must be an object")
            component_name = str(selection.get("name") or "").strip()
            if not component_name:
                raise ValueError(f"components[{index}].name is required")
            component_id = str(selection.get("component_id") or "").strip() or None
            selection_mode = str(selection.get("selection") or "").strip().lower() or None
            if selection_mode not in {None, "reuse", "new"}:
                raise ValueError(
                    f"components[{index}].selection must be reuse or new"
                )
            if selection_mode == "reuse" and not component_id:
                raise ValueError(
                    f"components[{index}].component_id is required for reuse"
                )
            if selection_mode == "new" and component_id:
                raise ValueError(
                    f"components[{index}].component_id must be empty for new variant"
                )
            normalized_selection: dict[str, str | None] = {
                "name": component_name,
                "component_id": component_id,
                "role": str(selection.get("role") or "component").strip() or "component",
            }
            if selection_mode is not None:
                normalized_selection["selection"] = selection_mode
            normalized_selections.append(normalized_selection)

        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "menu_id": str(menu_id),
                    "menu_detail_id": str(menu_detail_id),
                    "composition_name": name_value,
                    "library_group": library_group,
                    "components": normalized_selections,
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        site_scope = ObjectScope(
            tenant_id=actor.tenant_id,
            owner_scope="site",
            owner_site_id=str(actor.site_id).strip(),
            owner_user_id=None,
            visibility="site",
            source_object_id=None,
        )

        with builder_transaction(self._library_flow.database_path) as conn:
            menu = self._menu_service.get_menu(str(menu_id))
            if menu is None:
                raise ValueError("menu not found")
            if str(menu.site_id or "") != str(actor.site_id):
                raise ValueError("menu is outside the authenticated site")
            if str(menu.status or "").lower() == "published":
                raise ValueError("published menus cannot be changed")

            details = self._menu_service.list_menu_details(str(menu_id))
            detail = next(
                (item for item in details if item.menu_detail_id == str(menu_detail_id)),
                None,
            )
            if detail is None:
                raise ValueError("menu_detail_id not found for menu")

            existing_request = conn.execute(
                """
                SELECT idempotency_key, payload_hash, composition_id
                FROM builder_review_idempotency
                WHERE tenant_id = ?
                  AND site_id = ?
                  AND menu_id = ?
                  AND menu_detail_id = ?
                """,
                (
                    actor.tenant_id,
                    str(actor.site_id),
                    str(menu_id),
                    str(menu_detail_id),
                ),
            ).fetchone()
            if existing_request is not None:
                if str(existing_request["idempotency_key"]) != key_value:
                    raise ReviewedCompositionConflict(
                        "menu row already has a reviewed creation with a different idempotency key"
                    )
                if str(existing_request["payload_hash"]) != payload_hash:
                    raise ReviewedCompositionConflict(
                        "idempotency key was already used with a different payload"
                    )
                if (
                    detail.composition_ref_type != "composition"
                    or str(detail.composition_id or "") != str(existing_request["composition_id"])
                ):
                    raise ReviewedCompositionConflict(
                        "menu row state conflicts with the original reviewed creation"
                    )
                composition = self._library_flow.get_library_composition(
                    str(existing_request["composition_id"]),
                    actor=actor,
                )
                if composition is None:
                    raise ReviewedCompositionConflict(
                        "original reviewed composition is no longer available"
                    )
                return composition, detail

            if detail.composition_ref_type != "unresolved":
                raise ReviewedCompositionConflict("menu row is no longer unresolved")

            resolved_components: list[tuple[str, str, str, str | None]] = []
            for index, selection in enumerate(normalized_selections):
                component_name = str(selection["name"])
                component_id = selection["component_id"]
                selection_mode = selection.get("selection")
                if component_id:
                    component = self._library_flow.get_library_component(
                        component_id,
                        actor=actor,
                    )
                    if component is None:
                        raise ValueError(
                            f"components[{index}].component_id is not accessible"
                        )
                    resolved_components.append(
                        (
                            component.component_id,
                            component.canonical_name,
                            str(selection["role"]),
                            selection_mode,
                        )
                    )
                    continue

                if selection_mode == "new":
                    resolved_components.append(
                        ("", component_name, str(selection["role"]), selection_mode)
                    )
                    continue

                match = self._library_flow.match_component_name(
                    component_name,
                    actor=actor,
                )
                if match.status == "possible_match":
                    raise ReviewedCompositionConflict(
                        f"components[{index}] requires an explicit match selection"
                    )
                if match.status in {"exact_match", "alias_match"} and match.component_id:
                    component = self._library_flow.get_library_component(
                        match.component_id,
                        actor=actor,
                    )
                    if component is not None:
                        resolved_components.append(
                            (
                                component.component_id,
                                component.canonical_name,
                                str(selection["role"]),
                                selection_mode,
                            )
                        )
                        continue
                resolved_components.append(
                    ("", component_name, str(selection["role"]), selection_mode)
                )

            composition = self._library_flow.create_site_composition_with_generated_id(
                composition_name=name_value,
                library_group=library_group,
                seed_components=False,
                actor=actor,
            )
            for component_id, component_name, role, selection_mode in resolved_components:
                if not component_id:
                    component = self._library_flow.create_standalone_component(
                        component_name,
                        actor=actor,
                        scope=site_scope,
                        force_new=selection_mode == "new",
                    )
                    component_id = component.component_id
                    component_name = component.canonical_name
                composition = self._library_flow.attach_existing_component_to_composition(
                    composition_id=composition.composition_id,
                    component_id=component_id,
                    role=role,
                    actor=actor,
                )

            updated = self.resolve_menu_detail(
                menu_id=str(menu_id),
                menu_detail_id=str(menu_detail_id),
                composition_id=composition.composition_id,
                actor=actor,
                require_site_scope=True,
            )
            conn.execute(
                """
                INSERT INTO builder_review_idempotency (
                    idempotency_key, tenant_id, site_id, menu_id, menu_detail_id,
                    payload_hash, composition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_value,
                    actor.tenant_id,
                    str(actor.site_id),
                    str(menu_id),
                    str(menu_detail_id),
                    payload_hash,
                    composition.composition_id,
                ),
            )
            return composition, updated

    def get_menu_cost_overview(
        self,
        menu_id: str,
        *,
        default_target_portions: int = 1,
        target_portions_by_detail: dict[str, int] | None = None,
    ) -> MenuCostOverview:
        details = self._menu_service.list_menu_details(menu_id)
        detail_costs: list[MenuDetailCostBreakdown] = []
        warnings: list[str] = []
        unresolved_count = 0

        targets = target_portions_by_detail or {}
        for detail in details:
            if detail.composition_ref_type == "empty":
                continue
            target_portions = int(targets.get(detail.menu_detail_id, default_target_portions))
            breakdown = calculate_menu_detail_cost(
                menu_detail=detail,
                composition_repository=self._composition_repository,
                recipe_repository=self._recipe_repository,
                ingredient_repository=self._ingredient_repository,
                target_portions=target_portions,
            )
            detail_costs.append(breakdown)
            if detail.composition_ref_type == "unresolved":
                unresolved_count += 1
            warnings.extend(breakdown.warnings)

        if unresolved_count > 0:
            warnings.append("menu contains unresolved details")

        return MenuCostOverview(
            menu_id=menu_id,
            detail_costs=detail_costs,
            unresolved_count=unresolved_count,
            warnings=warnings,
        )
