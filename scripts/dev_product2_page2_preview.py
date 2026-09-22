from __future__ import annotations

"""Development-only preview seeder for Product2 Page2.

Usage:
  python scripts/dev_product2_page2_preview.py seed
  python scripts/dev_product2_page2_preview.py cleanup

This script creates one deterministic preview site and one published
Product2 lunch menu so UX can be inspected locally in the real route.
"""

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
import sys
from typing import Iterable

from flask import current_app
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import create_app
from core.admin_repo import DepartmentsRepo
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_publication import CommunBuilderPublicationService
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_menu_choice_repo import MenuChoiceRepo
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB
from core.models import Tenant
from core.planera_product2_page2_context import build_product2_page2_planning_context


PREVIEW_TENANT_ID = 1
PREVIEW_TENANT_NAME = "Preview Tenant"
PREVIEW_SITE_ID = "centralkoket-product2-preview"
PREVIEW_SITE_NAME = "Centralköket — Product2 Preview"
PREVIEW_DATE = _date(2026, 9, 8)
PREVIEW_MEAL = "lunch"
PREVIEW_MENU_ID = "product2-preview-menu"
PREVIEW_MENU_TITLE = "Product2 Preview Menu"
PREVIEW_BUDGET_VERSION = 1

PREVIEW_COMPOSITIONS = (
    ("product2-preview-comp-alt1", "Fläskkarré", "alt1", 10),
    ("product2-preview-comp-alt2", "Kokt torsk", "alt2", 20),
    ("product2-preview-comp-alt3", "Vegetarisk gryta", "alt3", 30),
)

PREVIEW_REQUIREMENT_TYPES = (
    ("preview_glutenfri", "Glutenfri"),
    ("preview_timbal", "Timbal"),
    ("preview_vegetarisk", "Vegetarisk"),
    ("preview_aggfri", "Äggfri"),
)

PREVIEW_DEPARTMENTS = (
    ("Avdelning A", 18, "alt1"),
    ("Avdelning B", 12, "alt2"),
    ("Avdelning C", 16, None),
)

PREVIEW_GROUP_PLAN = {
    "Avdelning A": (("Glutenfri", 3), ("Vegetarisk", 4)),
    "Avdelning B": (("Timbal", 2),),
    "Avdelning C": (("Äggfri", 1),),
}


@dataclass(frozen=True)
class PreviewRefs:
    site_id: str
    department_ids: dict[str, str]
    requirement_type_ids: dict[str, int]
    requirement_group_ids: dict[str, str]
    legacy_menu_id: int
    builder_menu_id: str


def _ensure_tenant(db) -> None:
    row = db.execute(text("SELECT id FROM tenants WHERE id=:id"), {"id": PREVIEW_TENANT_ID}).fetchone()
    if row is None:
        db.execute(
            text("INSERT INTO tenants(id, name, active) VALUES(:id, :name, 1)"),
            {"id": PREVIEW_TENANT_ID, "name": PREVIEW_TENANT_NAME},
        )


def _table_exists(db, table_name: str) -> bool:
    row = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    if row is not None:
        return True
    try:
        row = db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name=:name LIMIT 1"),
            {"name": table_name},
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _query_site_ids(db) -> list[str]:
    rows = db.execute(
        text("SELECT id FROM sites WHERE id=:id OR lower(trim(name)) = lower(trim(:name))"),
        {"id": PREVIEW_SITE_ID, "name": PREVIEW_SITE_NAME},
    ).fetchall()
    site_ids: list[str] = []
    for row in rows:
        site_id = str(row[0] or "").strip()
        if site_id and site_id not in site_ids:
            site_ids.append(site_id)
    return site_ids


def _query_department_ids(db, site_id: str) -> list[str]:
    rows = db.execute(
        text("SELECT id FROM departments WHERE site_id=:site_id ORDER BY name ASC, id ASC"),
        {"site_id": site_id},
    ).fetchall()
    return [str(row[0]) for row in rows if str(row[0] or "").strip()]


def _query_requirement_group_ids(db, department_ids: Iterable[str]) -> list[str]:
    dept_list = [str(value) for value in department_ids if str(value).strip()]
    if not dept_list:
        return []
    placeholders = ",".join(f":d{i}" for i in range(len(dept_list)))
    params = {f"d{i}": dept_id for i, dept_id in enumerate(dept_list)}
    rows = db.execute(
        text(f"SELECT id FROM department_requirement_groups WHERE department_id IN ({placeholders})"),
        params,
    ).fetchall()
    return [str(row[0]) for row in rows if str(row[0] or "").strip()]


def _query_requirement_type_ids(db, site_id: str) -> list[int]:
    rows = db.execute(
        text("SELECT id FROM dietary_types WHERE site_id=:site_id ORDER BY id ASC"),
        {"site_id": site_id},
    ).fetchall()
    return [int(row[0]) for row in rows if row[0] is not None]


def _delete_exact_rows(db, table_name: str, column_name: str, values: Iterable[str]) -> None:
    if not _table_exists(db, table_name):
        return
    clean_values = [str(value) for value in values if str(value).strip()]
    if not clean_values:
        return
    placeholders = ",".join(f":v{i}" for i in range(len(clean_values)))
    params = {f"v{i}": value for i, value in enumerate(clean_values)}
    db.execute(text(f"DELETE FROM {table_name} WHERE {column_name} IN ({placeholders})"), params)


def _delete_preview_dataset() -> PreviewRefs | None:
    db = get_session()
    try:
        _ensure_tenant(db)
        site_ids = _query_site_ids(db)
        if not site_ids:
            return None

        requirement_type_ids: dict[str, int] = {}
        department_ids_by_site: dict[str, list[str]] = {}
        group_ids_by_site: dict[str, list[str]] = {}
        legacy_menu_ids: list[str] = []

        for site_id in site_ids:
            dept_ids = _query_department_ids(db, site_id)
            department_ids_by_site[site_id] = dept_ids
            group_ids_by_site[site_id] = _query_requirement_group_ids(db, dept_ids)
            if dept_ids:
                _delete_exact_rows(db, "department_menu_choices", "department_id", dept_ids)
                _delete_exact_rows(db, "weekview_registrations", "department_id", dept_ids)
                _delete_exact_rows(db, "weekview_residents_count", "department_id", dept_ids)
                _delete_exact_rows(db, "weekview_alt2_flags", "department_id", dept_ids)

            # Collect requirement type ids before deleting preview-specific rows.
            for req_id in _query_requirement_type_ids(db, site_id):
                requirement_type_ids[str(req_id)] = req_id

            if group_ids_by_site[site_id]:
                _delete_exact_rows(db, "department_requirement_group_requirements", "group_id", group_ids_by_site[site_id])
                _delete_exact_rows(db, "department_requirement_groups", "id", group_ids_by_site[site_id])

        # Remove publication and menu linkage before menu + builder rows.
        db.execute(
            text("DELETE FROM commun_builder_publication_pins WHERE site_id=:site_id"),
            {"site_id": PREVIEW_SITE_ID},
        )
        db.execute(
            text("DELETE FROM commun_builder_menu_links WHERE site_id=:site_id"),
            {"site_id": PREVIEW_SITE_ID},
        )

        if _table_exists(db, "menus"):
            legacy_rows = db.execute(
                text("SELECT id FROM menus WHERE site_id=:site_id AND year=:year AND week=:week"),
                {
                    "site_id": PREVIEW_SITE_ID,
                    "year": PREVIEW_DATE.isocalendar()[0],
                    "week": PREVIEW_DATE.isocalendar()[1],
                },
            ).fetchall()
            legacy_menu_ids = [str(row[0]) for row in legacy_rows if str(row[0] or "").strip()]
            if legacy_menu_ids:
                _delete_exact_rows(db, "menu_variants", "menu_id", legacy_menu_ids)
                _delete_exact_rows(db, "menus", "id", legacy_menu_ids)

        if _table_exists(db, "builder_menu_rows"):
            db.execute(
                text("DELETE FROM builder_menu_rows WHERE menu_id=:menu_id"),
                {"menu_id": PREVIEW_MENU_ID},
            )
        if _table_exists(db, "builder_menus"):
            db.execute(
                text("DELETE FROM builder_menus WHERE menu_id=:menu_id"),
                {"menu_id": PREVIEW_MENU_ID},
            )
        if _table_exists(db, "builder_compositions"):
            for composition_id, _composition_name, _variant, _sort_order in PREVIEW_COMPOSITIONS:
                db.execute(
                    text("DELETE FROM builder_compositions WHERE composition_id=:composition_id"),
                    {"composition_id": composition_id},
                )

        # Delete requirement types after groups are gone.
        if _table_exists(db, "dietary_types"):
            db.execute(
                text("DELETE FROM dietary_types WHERE site_id=:site_id"),
                {"site_id": PREVIEW_SITE_ID},
            )

        # Delete departments and the site last.
        for site_id, dept_ids in department_ids_by_site.items():
            if dept_ids:
                _delete_exact_rows(db, "departments", "id", dept_ids)
            db.execute(text("DELETE FROM sites WHERE id=:site_id"), {"site_id": site_id})

        db.commit()
        if not site_ids:
            return None
        return PreviewRefs(
            site_id=PREVIEW_SITE_ID,
            department_ids={},
            requirement_type_ids=requirement_type_ids,
            requirement_group_ids={},
            legacy_menu_id=int(legacy_menu_ids[0]) if legacy_menu_ids else 0,
            builder_menu_id=PREVIEW_MENU_ID,
        )
    finally:
        db.close()


def _seed_site_and_departments() -> tuple[str, dict[str, str]]:
    db = get_session()
    try:
        _ensure_tenant(db)
        db.execute(
            text(
                "INSERT INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"
            ),
            {"id": PREVIEW_SITE_ID, "name": PREVIEW_SITE_NAME, "tenant_id": PREVIEW_TENANT_ID},
        )
        db.commit()
    finally:
        db.close()

    dept_repo = DepartmentsRepo()
    department_ids: dict[str, str] = {}
    for dept_name, resident_count, _choice in PREVIEW_DEPARTMENTS:
        department, _version = dept_repo.create_department(
            site_id=PREVIEW_SITE_ID,
            name=dept_name,
            resident_count_mode="fixed",
            resident_count_fixed=resident_count,
        )
        department_ids[dept_name] = str(department["id"])
    return PREVIEW_SITE_ID, department_ids


def _seed_requirement_types(site_id: str) -> dict[str, int]:
    db = get_session()
    try:
        requirement_type_ids: dict[str, int] = {}
        for requirement_key, name in PREVIEW_REQUIREMENT_TYPES:
            db.execute(
                text(
                    """
                    INSERT INTO dietary_types(
                        tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select
                    ) VALUES (:tenant_id, :site_id, :name, 'Övrigt', :requirement_key, 'atomic', 0)
                    """
                ),
                {
                    "tenant_id": PREVIEW_TENANT_ID,
                    "site_id": site_id,
                    "name": name,
                    "requirement_key": requirement_key,
                },
            )
        db.commit()
        for requirement_key, _name in PREVIEW_REQUIREMENT_TYPES:
            row = db.execute(
                text("SELECT id FROM dietary_types WHERE requirement_key=:requirement_key AND site_id=:site_id"),
                {"requirement_key": requirement_key, "site_id": site_id},
            ).fetchone()
            if row is None:
                raise RuntimeError(f"failed to seed dietary type {requirement_key}")
            requirement_type_ids[requirement_key] = int(row[0])
        return requirement_type_ids
    finally:
        db.close()


def _seed_requirement_groups(department_ids: dict[str, str], requirement_type_ids: dict[str, int]) -> dict[str, str]:
    repo = DepartmentRequirementGroupsRepo()
    group_ids: dict[str, str] = {}
    name_to_key = {name: key for key, name in PREVIEW_REQUIREMENT_TYPES}
    for department_name, groups in PREVIEW_GROUP_PLAN.items():
        department_id = department_ids[department_name]
        for requirement_name, quantity in groups:
            requirement_id = requirement_type_ids[name_to_key[requirement_name]]
            group = repo.create_group(
                department_id=department_id,
                default_quantity=quantity,
                requirement_ids=[requirement_id],
                label=requirement_name,
            )
            group_ids[str(group["id"])] = department_name
    return group_ids


def _seed_menu_choices(department_ids: dict[str, str]) -> None:
    choice_repo = MenuChoiceRepo()
    year, week, weekday = PREVIEW_DATE.isocalendar()
    day_number = int(weekday)
    for department_name, _resident_count, selected_alt in PREVIEW_DEPARTMENTS:
        if not selected_alt:
            continue
        choice_repo.set_choice(
            tenant_id=PREVIEW_TENANT_ID,
            site_id=PREVIEW_SITE_ID,
            department_id=department_ids[department_name],
            year=int(year),
            week=int(week),
            weekday=day_number,
            selected_alt=selected_alt,
            meal=PREVIEW_MEAL,
        )


def _build_builder_flow() -> tuple[BuilderFlow, CompositionService, BuilderMenuContextFlow]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=InMemoryComponentAliasRepository(),
    )
    menu_context_flow = MenuService(
        composition_repository=composition_repository,
    )
    flow = BuilderMenuContextFlow(
        menu_service=menu_context_flow,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return builder_flow, CompositionService(repository=composition_repository), flow


def _seed_published_menu(app) -> int:
    year, week, _weekday = PREVIEW_DATE.isocalendar()
    builder_flow, composition_service, menu_context_flow = _build_builder_flow()
    with app.app_context():
        current_app.extensions["builder_menu_context_flow"] = menu_context_flow
        current_app.extensions["builder_flow"] = builder_flow

        menu_context_flow.create_menu(
            menu_id=PREVIEW_MENU_ID,
            site_id=PREVIEW_SITE_ID,
            week_key=f"{year}-W{week:02d}",
            version=PREVIEW_BUDGET_VERSION,
            status="published",
            title=PREVIEW_MENU_TITLE,
        )
        for composition_id, composition_name, variant_type, sort_order in PREVIEW_COMPOSITIONS:
            composition_service.create_composition(
                composition_id=composition_id,
                composition_name=composition_name,
            )
            menu_context_flow.add_composition_menu_row(
                menu_id=PREVIEW_MENU_ID,
                day="tuesday",
                meal_slot=f"lunch_{variant_type}",
                composition_id=composition_id,
                sort_order=sort_order,
            )

        link_service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
        menu_service = MenuServiceDB()
        legacy_menu = menu_service.create_or_get_menu(
            tenant_id=PREVIEW_TENANT_ID,
            site_id=PREVIEW_SITE_ID,
            week=int(week),
            year=int(year),
        )
        link_service.create_or_replace_link(
            tenant_id=PREVIEW_TENANT_ID,
            site_id=PREVIEW_SITE_ID,
            year=int(year),
            week=int(week),
            builder_menu_id=PREVIEW_MENU_ID,
            legacy_menu_id=int(legacy_menu.id),
            source="manual",
        )
        menu_service.publish_menu(tenant_id=PREVIEW_TENANT_ID, menu_id=int(legacy_menu.id))
        return int(legacy_menu.id)


def _seed() -> None:
    app = create_app()
    with app.app_context():
        _delete_preview_dataset()

    site_id, department_ids = _seed_site_and_departments()
    requirement_type_ids = _seed_requirement_types(site_id)
    requirement_group_ids = _seed_requirement_groups(department_ids, requirement_type_ids)
    _seed_menu_choices(department_ids)

    app = create_app()
    with app.app_context():
        legacy_menu_id = _seed_published_menu(app)
        context = build_product2_page2_planning_context(
            tenant_id=PREVIEW_TENANT_ID,
            site_id=PREVIEW_SITE_ID,
            service_date=PREVIEW_DATE,
            meal=PREVIEW_MEAL,
        )

    print("PAGE2 PREVIEW READY")
    print(f"Site:\n{PREVIEW_SITE_NAME}")
    print(f"Site ID:\n{PREVIEW_SITE_ID}")
    print(f"Date:\n{PREVIEW_DATE.isoformat()}")
    print(
        "URL:\n"
        f"http://127.0.0.1:5000/ui/kitchen/planering/day?ui=product2&site_id={PREVIEW_SITE_ID}&date={PREVIEW_DATE.isoformat()}&meal=lunch"
    )
    print("\nPublished options:")
    for option in context.options:
        print(f"- {option.display_label}: {option.display_title} ({option.option_id})")
    print("\nDestinations:")
    for destination in context.destinations:
        selected_label = "Inget explicit menyval"
        if destination.selected_option_id:
            selected_option = next((option for option in context.options if option.option_id == destination.selected_option_id), None)
            if selected_option is not None:
                selected_label = f"Vald meny: {selected_option.display_label} · {selected_option.display_title}"
        print(f"- {destination.display_name} | baseline={destination.baseline_quantity} | {selected_label}")
    print("\nRequirement groups:")
    for group in context.requirement_groups:
        req_text = ", ".join(
            f"{req.name} ({req.requirement_key or req.dietary_type_id})" for req in group.requirements
        )
        print(
            f"- {group.destination_id} | {group.label or group.requirement_group_id} | quantity={group.effective_quantity} | {req_text}"
        )
    print("\nSeed command:\npython scripts/dev_product2_page2_preview.py seed")
    print("Cleanup command:\npython scripts/dev_product2_page2_preview.py cleanup")
    print("\nPreview data intentionally remains in dev.db.")


def _cleanup() -> None:
    app = create_app()
    with app.app_context():
        deleted = _delete_preview_dataset()
    if deleted is None:
        print("Cleanup complete. No preview dataset found.")
    else:
        print("Cleanup complete. Preview dataset removed.")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"seed", "cleanup"}:
        print("Usage: python scripts/dev_product2_page2_preview.py seed|cleanup")
        return 1
    if argv[1] == "seed":
        _seed()
    else:
        _cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))