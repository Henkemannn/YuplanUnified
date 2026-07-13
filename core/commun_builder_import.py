from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from flask import current_app, has_app_context

from .builder_menu_context_flow import BuilderMenuContextFlow
from .commun_builder_linkage import CommunBuilderMenuLinkService
from .importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from .menu import ImportedMenuRow, resolve_composition_reference
from .menu.menu_domain import Menu, MenuDetail


@dataclass(frozen=True)
class CommunBuilderCanonicalImportOutcome:
    menu_id: str
    year: int
    week: int
    status: str
    imported_count: int
    resolved_count: int
    unresolved_count: int
    builder_menu_version: int
    warnings: list[str]


@dataclass(frozen=True)
class _WeekSnapshot:
    menu: Menu | None
    details: list[MenuDetail]
    link: Any | None
    tenant_id: int
    site_id: str
    year: int
    week: int


class CommunBuilderCanonicalImportError(RuntimeError):
    def __init__(self, message: str, *, recovery_state: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.recovery_state = recovery_state or {}


def build_canonical_menu_id(*, tenant_id: int, site_id: str, year: int, week: int, import_type: str) -> str:
    components = [
        "builder-menu",
        _slug_component(str(tenant_id)),
        _slug_component(site_id),
        f"{int(year):04d}",
        f"w{int(week):02d}",
        _slug_component(import_type or "menu"),
    ]
    return "-".join(component for component in components if component)


def import_menu_result_to_builder_canonical(
    import_result: MenuImportResult,
    *,
    tenant_id: int,
    site_id: str,
    import_type: str = "menu",
) -> list[CommunBuilderCanonicalImportOutcome]:
    flow = _get_builder_menu_context_flow()
    linkage_service = CommunBuilderMenuLinkService(builder_menu_context_flow=flow)

    snapshots: dict[str, _WeekSnapshot] = {}
    outcomes: list[CommunBuilderCanonicalImportOutcome] = []
    for week_import in import_result.weeks:
        menu_id = build_canonical_menu_id(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=week_import.year,
            week=week_import.week,
            import_type=import_type,
        )
        snapshots[menu_id] = _snapshot_week_state(
            flow,
            linkage_service,
            menu_id,
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(week_import.year),
            week=int(week_import.week),
        )

    try:
        for week_import in import_result.weeks:
            outcome = _import_week(
                flow,
                linkage_service,
                week_import,
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                import_type=import_type,
                import_warnings=list(import_result.warnings),
            )
            outcomes.append(outcome)
        return outcomes
    except Exception as exc:
        _restore_snapshots(flow, linkage_service, snapshots)
        raise CommunBuilderCanonicalImportError("canonical import failed", recovery_state={"restored": True}) from exc


def _import_week(
    flow: BuilderMenuContextFlow,
    linkage_service: CommunBuilderMenuLinkService,
    week_import: WeekImport,
    *,
    tenant_id: int,
    site_id: str,
    import_type: str,
    import_warnings: list[str],
) -> CommunBuilderCanonicalImportOutcome:
    menu_id = build_canonical_menu_id(
        tenant_id=tenant_id,
        site_id=site_id,
        year=week_import.year,
        week=week_import.week,
        import_type=import_type,
    )
    week_key = f"{int(week_import.year):04d}-W{int(week_import.week):02d}"

    desired_rows, row_warnings, resolved_count, unresolved_count = _build_desired_rows(week_import, flow)
    existing_menu = flow._menu_service.get_menu(menu_id)
    existing_rows = list(flow.list_menu_rows(menu_id)) if existing_menu is not None else []

    if existing_menu is None:
        flow.create_menu(menu_id=menu_id, site_id=site_id, week_key=week_key, version=1, status="created")
        menu_status = "created"
        menu_version = 1
    else:
        if _row_signatures(existing_rows) == _row_signatures(desired_rows):
            builder_menu = existing_menu
            return CommunBuilderCanonicalImportOutcome(
                menu_id=menu_id,
                year=int(week_import.year),
                week=int(week_import.week),
                status="unchanged",
                imported_count=len(desired_rows),
                resolved_count=resolved_count,
                unresolved_count=unresolved_count,
                builder_menu_version=int(getattr(builder_menu, "version", 0) or 0),
                warnings=list(import_warnings) + row_warnings,
            )
        menu_version = int(getattr(existing_menu, "version", 0) or 0) + 1
        flow._menu_service.update_menu(menu_id, version=menu_version, status="updated")
        menu_status = "updated"

        for row in existing_rows:
            flow.delete_menu_row(menu_id=menu_id, menu_detail_id=str(row.get("menu_detail_id") or ""))

    for index, row in enumerate(desired_rows, start=1):
        flow._menu_service.add_menu_detail(
            menu_detail_id=f"{menu_id}-import-{index}",
            menu_id=menu_id,
            day=str(row["day"]),
            meal_slot=str(row["meal_slot"]),
            composition_ref_type=str(row["composition_ref_type"]),
            composition_id=row.get("composition_id"),
            unresolved_text=row.get("unresolved_text"),
            note=row.get("note"),
            sort_order=int(row["sort_order"]),
        )

    builder_menu = flow._menu_service.get_menu(menu_id)
    if builder_menu is None:
        raise RuntimeError("builder menu missing after canonical import")

    linkage_service.create_or_replace_link(
        tenant_id=tenant_id,
        site_id=site_id,
        year=int(week_import.year),
        week=int(week_import.week),
        builder_menu_id=menu_id,
        source="pilot",
    )

    return CommunBuilderCanonicalImportOutcome(
        menu_id=menu_id,
        year=int(week_import.year),
        week=int(week_import.week),
        status=menu_status,
        imported_count=len(desired_rows),
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        builder_menu_version=int(getattr(builder_menu, "version", 0) or 0),
        warnings=list(import_warnings) + row_warnings,
    )


def _snapshot_week_state(
    flow: BuilderMenuContextFlow,
    linkage_service: CommunBuilderMenuLinkService,
    menu_id: str,
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
) -> _WeekSnapshot:
    menu = flow._menu_service.get_menu(menu_id)
    details = list(flow.list_menu_rows(menu_id)) if menu is not None else []
    link = linkage_service.get_link_for_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
    return _WeekSnapshot(
        menu=menu,
        details=[_to_menu_detail(detail) for detail in details],
        link=link,
        tenant_id=int(tenant_id),
        site_id=str(site_id),
        year=int(year),
        week=int(week),
    )


def _restore_snapshots(
    flow: BuilderMenuContextFlow,
    linkage_service: CommunBuilderMenuLinkService,
    snapshots: dict[str, _WeekSnapshot],
) -> None:
    for menu_id, snapshot in snapshots.items():
        current_menu = flow._menu_service.get_menu(menu_id)
        if current_menu is not None:
            try:
                flow._menu_service.delete_menu(menu_id)
            except Exception:
                pass
        if snapshot.menu is not None:
            flow.create_menu(
                menu_id=snapshot.menu.menu_id,
                site_id=snapshot.menu.site_id,
                week_key=snapshot.menu.week_key,
                title=snapshot.menu.title,
                version=snapshot.menu.version,
                status=snapshot.menu.status,
            )
            for detail in snapshot.details:
                flow._menu_service.add_menu_detail(
                    menu_detail_id=detail.menu_detail_id,
                    menu_id=detail.menu_id,
                    day=detail.day,
                    meal_slot=detail.meal_slot,
                    composition_ref_type=detail.composition_ref_type,
                    composition_id=detail.composition_id,
                    unresolved_text=detail.unresolved_text,
                    note=detail.note,
                    sort_order=detail.sort_order,
                )
        if snapshot.link is None:
            try:
                linkage_service.delete_link(
                    tenant_id=snapshot.tenant_id,
                    site_id=snapshot.site_id,
                    year=snapshot.year,
                    week=snapshot.week,
                )
            except Exception:
                pass
        else:
            try:
                linkage_service.create_or_replace_link(
                    tenant_id=int(snapshot.link.tenant_id),
                    site_id=str(snapshot.link.site_id),
                    year=int(snapshot.link.year),
                    week=int(snapshot.link.week),
                    builder_menu_id=str(snapshot.link.builder_menu_id),
                    legacy_menu_id=snapshot.link.legacy_menu_id,
                    source=str(snapshot.link.source),
                    projection_version=int(snapshot.link.projection_version),
                )
            except Exception:
                pass


def _canonical_meal_slot(item: ImportedMenuItem) -> str:
    meal = str(item.meal or "").strip().lower()
    variant = str(item.variant_type or "").strip().lower()

    if meal == "evening":
        meal = "dinner"
        variant = "main"

    if variant == "main":
        return f"{meal}_main"
    if variant in {"alt1", "alt2", "dessert"}:
        return f"{meal}_{variant}"
    raise ValueError(f"unsupported variant_type: {variant or '<empty>'}")


def _build_desired_rows(
    week_import: WeekImport,
    flow: BuilderMenuContextFlow,
) -> tuple[list[dict[str, Any]], list[str], int, int]:
    desired_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    resolved_count = 0
    unresolved_count = 0

    for index, item in enumerate(week_import.items, start=1):
        meal_slot = _canonical_meal_slot(item)
        resolution = resolve_composition_reference(
            import_text=str(item.dish_name or ""),
            composition_repository=flow._composition_repository,
            alias_repository=flow._alias_repository,
        )
        if resolution.kind != "composition" or resolution.composition_id is None:
            desired_rows.append(
                {
                    "day": str(item.day or ""),
                    "meal_slot": meal_slot,
                    "composition_ref_type": "unresolved",
                    "composition_id": None,
                    "unresolved_text": str(item.dish_name or ""),
                    "note": None,
                    "sort_order": index * 10,
                }
            )
            unresolved_count += 1
            continue

        composition = flow._composition_repository.get(resolution.composition_id)
        if composition is None:
            warnings.append("resolved composition missing; stored as unresolved")
            desired_rows.append(
                {
                    "day": str(item.day or ""),
                    "meal_slot": meal_slot,
                    "composition_ref_type": "unresolved",
                    "composition_id": None,
                    "unresolved_text": str(item.dish_name or ""),
                    "note": None,
                    "sort_order": index * 10,
                }
            )
            unresolved_count += 1
            continue

        desired_rows.append(
            {
                "day": str(item.day or ""),
                "meal_slot": meal_slot,
                "composition_ref_type": "composition",
                "composition_id": composition.composition_id,
                "unresolved_text": None,
                "note": None,
                "sort_order": index * 10,
            }
        )
        resolved_count += 1

    if unresolved_count > 0:
        warnings.append("one or more imported rows are unresolved")

    return desired_rows, warnings, resolved_count, unresolved_count


def _row_signatures(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            str(row.get("day") or "").strip(),
            str(row.get("meal_slot") or "").strip(),
            str(row.get("composition_ref_type") or "").strip(),
            str(row.get("composition_id") or "").strip(),
            str(row.get("unresolved_text") or "").strip(),
            str(row.get("note") or "").strip(),
            int(row.get("sort_order") or 0),
        )
        for row in rows
    ]


def _to_menu_detail(detail: dict[str, Any]) -> MenuDetail:
    return MenuDetail(
        menu_detail_id=str(detail.get("menu_detail_id") or ""),
        menu_id=str(detail.get("menu_id") or ""),
        day=str(detail.get("day") or ""),
        meal_slot=str(detail.get("meal_slot") or ""),
        composition_ref_type=str(detail.get("composition_ref_type") or ""),
        composition_id=detail.get("composition_id"),
        unresolved_text=detail.get("unresolved_text"),
        note=detail.get("note"),
        sort_order=int(detail.get("sort_order") or 0),
    )


def _year_week_from_menu_key(week_key: str) -> tuple[int, int]:
    match = re.match(r"^(\d{4})-W(\d{2})$", str(week_key or ""))
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _slug_component(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    return slug.strip("-")


def _get_builder_menu_context_flow() -> BuilderMenuContextFlow:
    flow = current_app.extensions.get("builder_menu_context_flow")
    if isinstance(flow, BuilderMenuContextFlow):
        return flow

    if not has_app_context():
        raise RuntimeError("builder_menu_context_flow_unavailable")

    from .builder_menu_context_api import _get_menu_context_flow

    return _get_menu_context_flow()


__all__ = [
    "CommunBuilderCanonicalImportOutcome",
    "build_canonical_menu_id",
    "import_menu_result_to_builder_canonical",
]