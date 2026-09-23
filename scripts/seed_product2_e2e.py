from __future__ import annotations

"""Seed a deterministic local Product2 E2E tenant/site.

This script is intentionally local-only and refuses to touch dev.db, pilot/prod,
or any Fly-backed environment. It creates a dedicated SQLite database pair for
the main app data and the builder library, then seeds a realistic municipal
tenant with canonical Product2 page2 data.
"""

from dataclasses import dataclass
from datetime import date
import os
import sys
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MAIN_DB_PATH = ROOT / "instance" / "product2_e2e.db"
BUILDER_DB_PATH = ROOT / "instance" / "product2_e2e_builder.db"
TENANT_ID = 1
TENANT_NAME = "Yuplan E2E Kommun"
SITE_NAME = "Centralköket E2E"
SITE_ID = "yuplan-e2e-centralkoket"
YEAR = 2026
WEEK = 37
SERVICE_DATE = date.fromisocalendar(YEAR, WEEK, 2)
MEAL = "lunch"
BUILDER_MENU_ID = "yuplan-e2e-product2-week37"
BUILDER_MENU_VERSION = 1
PUBLISHED_DAYS = ("tuesday",)
KITCHEN_USER_EMAIL = "e2e.kitchen@yuplan.local"
KITCHEN_USER_PASSWORD = "e2e-kitchen-pass"
OPTION_DEFINITIONS = (
    ("product2-e2e-alt1", "Alt 1", "Vardagsgryta med rotfrukter", "alt1", 10),
    ("product2-e2e-alt2", "Alt 2", "Ugnsbakad fisk med dill", "alt2", 20),
)
DEPARTMENT_DEFINITIONS = (
    ("Avdelning 01", 5),
    ("Avdelning 02", 6),
    ("Avdelning 03", 6),
    ("Avdelning 04", 7),
    ("Avdelning 05", 5),
    ("Avdelning 06", 7),
    ("Avdelning 07", 8),
    ("Avdelning 08", 8),
    ("Avdelning 09", 6),
    ("Avdelning 10", 9),
    ("Avdelning 11", 10),
    ("Avdelning 12", 7),
    ("Avdelning 13", 8),
    ("Avdelning 14", 9),
    ("Avdelning 15", 7),
    ("Avdelning 16", 10),
    ("Avdelning 17", 11),
    ("Avdelning 18", 12),
)
REQUIREMENT_DEFINITIONS = (
    ("Glutenfri", "glutenfri"),
    ("Laktosfri", "laktosfri"),
    ("Vegetarisk", "vegetarisk"),
    ("Timbal", "timbal"),
    ("Grovpaté", "grovpaté"),
    ("Äggfri", "äggfri"),
)
DEPARTMENT_GROUP_DEFINITIONS = {
    "Avdelning 01": [(("Glutenfri",), 1), (("Laktosfri",), 1)],
    "Avdelning 02": [(("Timbal",), 2)],
    "Avdelning 03": [(("Grovpaté",), 2)],
    "Avdelning 04": [(("Vegetarisk",), 1), (("Äggfri",), 1)],
    "Avdelning 05": [],
    "Avdelning 06": [(("Glutenfri", "Laktosfri"), 1)],
    "Avdelning 07": [(("Timbal",), 2), (("Grovpaté",), 1)],
    "Avdelning 08": [(("Äggfri",), 1)],
    "Avdelning 09": [],
    "Avdelning 10": [(("Vegetarisk",), 2)],
    "Avdelning 11": [(("Glutenfri",), 1), (("Laktosfri",), 1), (("Äggfri",), 1)],
    "Avdelning 12": [],
    "Avdelning 13": [(("Timbal", "Laktosfri"), 1)],
    "Avdelning 14": [],
    "Avdelning 15": [],
    "Avdelning 16": [(("Glutenfri",), 2), (("Vegetarisk", "Äggfri"), 1)],
    "Avdelning 17": [],
    "Avdelning 18": [(("Äggfri", "Laktosfri"), 1)],
}
MENU_CHOICES = {
    "Avdelning 01": [2],
    "Avdelning 02": [2],
    "Avdelning 03": [2],
    "Avdelning 04": [2],
    "Avdelning 05": [2],
    "Avdelning 06": [2],
    "Avdelning 07": [2],
    "Avdelning 08": [2],
    "Avdelning 09": [2],
    "Avdelning 10": [2],
    "Avdelning 11": [2],
    "Avdelning 12": [2],
    "Avdelning 13": [2],
    "Avdelning 14": [2],
    "Avdelning 15": [2],
    "Avdelning 16": [2],
    "Avdelning 17": [2],
}


@dataclass(frozen=True)
class SeedResult:
    tenant_id: int
    site_id: str
    main_db_path: str
    builder_db_path: str
    builder_menu_id: str
    year: int
    week: int
    service_date: str
    department_count: int
    option_count: int
    menu_choice_counts: dict[str, int]
    kitchen_user_email: str
    kitchen_user_role: str


def _normalize(value: object | None) -> str:
    return str(value or "").strip()


def _is_refused_environment() -> bool:
    raw = {
        "database_url": _normalize(os.getenv("DATABASE_URL")),
        "app_env": _normalize(os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("DEPLOY_ENV")),
        "fly": _normalize(os.getenv("FLY_APP_NAME") or os.getenv("FLY_REGION") or os.getenv("FLY_MACHINE_ID")),
    }
    if raw["app_env"].lower() in {"prod", "production", "pilot", "staging"}:
        return True
    if "fly.io" in raw["database_url"].lower() or raw["fly"]:
        return True
    if raw["database_url"] and "dev.db" in raw["database_url"].replace("/", "\\").lower():
        return True
    return False


def _prepare_paths() -> None:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MAIN_DB_PATH.exists():
        MAIN_DB_PATH.unlink()
    if BUILDER_DB_PATH.exists():
        BUILDER_DB_PATH.unlink()


def _configure_app_env() -> None:
    os.environ["APP_ENV"] = "local"
    os.environ["FLASK_ENV"] = "local"
    os.environ["DEPLOY_ENV"] = "local"
    os.environ["DATABASE_URL"] = f"sqlite:///{MAIN_DB_PATH.as_posix()}"
    os.environ["BUILDER_DB_PATH"] = str(BUILDER_DB_PATH)


def _build_builder_context():
    from core.app_factory import create_app
    from core.builder_sqlite import initialize_builder_sqlite

    initialize_builder_sqlite(str(BUILDER_DB_PATH))

    app = create_app({"TESTING": True, "database_url": f"sqlite:///{MAIN_DB_PATH.as_posix()}", "BUILDER_DB_PATH": str(BUILDER_DB_PATH)})
    return app


def _ensure_tenant_and_site() -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO tenants(id, name, active) VALUES(:id, :name, 1)"), {"id": TENANT_ID, "name": TENANT_NAME})
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tenant_id, 0)"
            ),
            {"id": SITE_ID, "name": SITE_NAME, "tenant_id": TENANT_ID},
        )
        db.commit()
    finally:
        db.close()


def _seed_kitchen_user() -> None:
    from core.auth import generate_password_hash
    from core.db import get_session

    db = get_session()
    try:
        row = db.execute(text("SELECT id FROM users WHERE lower(email)=:email"), {"email": KITCHEN_USER_EMAIL.lower()}).fetchone()
        password_hash = generate_password_hash(KITCHEN_USER_PASSWORD)
        if row is None:
            db.execute(
                text(
                    "INSERT INTO users(tenant_id, email, username, password_hash, role, full_name, is_active) "
                    "VALUES(:tenant_id, :email, :username, :password_hash, :role, :full_name, 1)"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "email": KITCHEN_USER_EMAIL.lower(),
                    "username": KITCHEN_USER_EMAIL.lower(),
                    "password_hash": password_hash,
                    "role": "kitchen",
                    "full_name": "E2E Kitchen User",
                },
            )
            row = db.execute(text("SELECT id FROM users WHERE lower(email)=:email"), {"email": KITCHEN_USER_EMAIL.lower()}).fetchone()
        else:
            db.execute(
                text(
                    "UPDATE users SET tenant_id=:tenant_id, username=:username, password_hash=:password_hash, role=:role, full_name=:full_name, is_active=1 "
                    "WHERE lower(email)=:email"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "email": KITCHEN_USER_EMAIL.lower(),
                    "username": KITCHEN_USER_EMAIL.lower(),
                    "password_hash": password_hash,
                    "role": "kitchen",
                    "full_name": "E2E Kitchen User",
                },
            )
        user_id = int(row[0]) if row else 0
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) VALUES(:uid, :tid, :sid) "
                "ON CONFLICT(user_id) DO UPDATE SET tenant_id=excluded.tenant_id, site_id=excluded.site_id"
            ),
            {"uid": user_id, "tid": TENANT_ID, "sid": SITE_ID},
        )
        db.commit()
    finally:
        db.close()


def _seed_departments() -> dict[str, dict[str, Any]]:
    from core.admin_repo import DepartmentsRepo

    repo = DepartmentsRepo()
    departments: dict[str, dict[str, Any]] = {}
    for index, (name, resident_count) in enumerate(DEPARTMENT_DEFINITIONS, start=1):
        department, _version = repo.create_department(
            site_id=SITE_ID,
            name=name,
            resident_count_mode="fixed",
            resident_count_fixed=resident_count,
        )
        departments[name] = department
    return departments


def _seed_requirements() -> dict[str, int]:
    from core.admin_repo import DietTypesRepo

    repo = DietTypesRepo()
    requirement_ids: dict[str, int] = {}
    for name, requirement_key in REQUIREMENT_DEFINITIONS:
        existing = next((row for row in repo.list_all(site_id=SITE_ID) if row["requirement_key"] == requirement_key), None)
        if existing is None:
            requirement_ids[name] = repo.create(site_id=SITE_ID, name=name, semantics="atomic", diet_family="Övrigt", default_select=False)
        else:
            requirement_ids[name] = int(existing["id"])
    return requirement_ids


def _seed_requirement_groups(departments: dict[str, dict[str, Any]], requirement_ids: dict[str, int]) -> list[dict[str, Any]]:
    from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo

    repo = DepartmentRequirementGroupsRepo()
    groups: list[dict[str, Any]] = []
    for department_name, group_definitions in DEPARTMENT_GROUP_DEFINITIONS.items():
        department_id = str(departments[department_name]["id"])
        for group_index, (requirement_names, default_quantity) in enumerate(group_definitions, start=1):
            requirement_set = [requirement_ids[name] for name in requirement_names]
            group = repo.create_group(
                department_id,
                default_quantity,
                requirement_set,
                label=f"{department_name} behov {group_index}",
            )
            groups.append(
                {
                    "department_name": department_name,
                    "group_id": str(group["id"]),
                    "group_index": group_index,
                    "default_quantity": int(default_quantity),
                    "requirement_names": requirement_names,
                }
            )
    return groups


def _seed_overrides(groups: list[dict[str, Any]]) -> None:
    from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo

    repo = DepartmentRequirementGroupServiceOverridesRepo()
    override_targets = {
        ("Avdelning 01", 1): 3,
        ("Avdelning 07", 1): 0,
        ("Avdelning 16", 1): 3,
    }
    for group in groups:
        key = (group["department_name"], int(group["group_index"]))
        if key not in override_targets:
            continue
        repo.set_override(group["group_id"], SERVICE_DATE, MEAL, override_targets[key])


def _seed_menu_choices(departments: dict[str, dict[str, Any]]) -> dict[str, int]:
    from core.department_menu_choice_repo import MenuChoiceRepo

    repo = MenuChoiceRepo()
    counts = {"alt1": 0, "alt2": 0}
    for department_name, weekday_list in MENU_CHOICES.items():
        department_id = str(departments[department_name]["id"])
        for weekday in weekday_list:
            selected_alt = "alt1" if int(department_name.split()[-1]) <= 10 else "alt2"
            repo.set_choice(
                tenant_id=TENANT_ID,
                site_id=SITE_ID,
                department_id=department_id,
                year=YEAR,
                week=WEEK,
                weekday=weekday,
                selected_alt=selected_alt,
            )
            counts[selected_alt] += 1
            counts["none"] = len(departments) - sum(counts.values())
    return counts


def _build_builder_flow():
    from core.builder import BuilderFlow
    from core.builder_menu_context_flow import BuilderMenuContextFlow
    from core.components import (
        ComponentService,
        CompositionService,
        InMemoryComponentAliasRepository,
        InMemoryComponentRepository,
        InMemoryCompositionRepository,
        InMemoryRecipeIngredientLineRepository,
        InMemoryRecipeRepository,
    )
    from core.menu import InMemoryCompositionAliasRepository, MenuService

    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=InMemoryCompositionAliasRepository(),
        component_alias_repository=InMemoryComponentAliasRepository(),
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=MenuService(composition_repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=InMemoryCompositionAliasRepository(),
        recipe_repository=InMemoryRecipeRepository(),
        ingredient_repository=InMemoryRecipeIngredientLineRepository(),
        library_flow=builder_flow,
    )
    return builder_flow, menu_context_flow


def _seed_publication(app) -> dict[str, str]:
    from core.commun_builder_linkage import CommunBuilderMenuLinkService
    from core.commun_builder_publication import CommunBuilderPublicationRepository
    from core.commun_builder_projection import get_shadow_projection_reader
    from core.menu_service import MenuServiceDB

    with app.app_context():
        builder_flow, menu_context_flow = _build_builder_flow()
        current_app.extensions["builder_flow"] = builder_flow
        current_app.extensions["builder_menu_context_flow"] = menu_context_flow
        current_app.extensions["builder_menu_service"] = menu_context_flow._menu_service

        menu_context_flow.create_menu(
            menu_id=BUILDER_MENU_ID,
            site_id=SITE_ID,
            week_key=f"{YEAR}-W{WEEK:02d}",
            version=BUILDER_MENU_VERSION,
            status="published",
        )
        for composition_id, _, title, variant_type, sort_order in OPTION_DEFINITIONS:
            builder_flow.create_composition(composition_id=composition_id, composition_name=title)
            menu_context_flow.add_composition_menu_row(
                menu_id=BUILDER_MENU_ID,
                day=PUBLISHED_DAYS[0],
                meal_slot=f"{MEAL}_{variant_type}",
                composition_id=composition_id,
                sort_order=sort_order,
            )

        link_service = CommunBuilderMenuLinkService(builder_menu_context_flow=menu_context_flow)
        legacy_menu_id = MenuServiceDB().create_or_get_menu(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            week=WEEK,
            year=YEAR,
        ).id
        link_service.create_or_replace_link(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            year=YEAR,
            week=WEEK,
            builder_menu_id=BUILDER_MENU_ID,
            legacy_menu_id=legacy_menu_id,
            source="manual",
        )

        from core.commun_builder_publication import CommunBuilderPublicationService

        publication = CommunBuilderPublicationService().publish_week(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            year=YEAR,
            week=WEEK,
            legacy_menu_id=legacy_menu_id,
        )
        if publication is None:
            raise RuntimeError("publication_missing")

        outcome = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            year=YEAR,
            week=WEEK,
            builder_menu_id=BUILDER_MENU_ID,
            builder_menu_version=BUILDER_MENU_VERSION,
        )
        if outcome.status != "ok" or outcome.projection is None:
            raise RuntimeError(f"publication_projection_failed:{outcome.error or outcome.status}")
        return {
            str(row.variant_type): str(row.builder_menu_row_id)
            for row in outcome.projection.rows
            if str(row.meal) == MEAL
        }


def _seed() -> SeedResult:
    _prepare_paths()
    _configure_app_env()
    app = _build_builder_context()
    with app.app_context():
        from core.db import create_all

        create_all()
        _ensure_tenant_and_site()
        departments = _seed_departments()
        requirement_ids = _seed_requirements()
        groups = _seed_requirement_groups(departments, requirement_ids)
        _seed_overrides(groups)
        menu_choice_counts = _seed_menu_choices(departments)
        option_ids = _seed_publication(app)
        _seed_kitchen_user()
        if len(option_ids) < 2:
            raise RuntimeError("published_menu_options_missing")
    return SeedResult(
        tenant_id=TENANT_ID,
        site_id=SITE_ID,
        main_db_path=str(MAIN_DB_PATH),
        builder_db_path=str(BUILDER_DB_PATH),
        builder_menu_id=BUILDER_MENU_ID,
        year=YEAR,
        week=WEEK,
        service_date=SERVICE_DATE.isoformat(),
        department_count=len(DEPARTMENT_DEFINITIONS),
        option_count=len(OPTION_DEFINITIONS),
        menu_choice_counts=menu_choice_counts,
        kitchen_user_email=KITCHEN_USER_EMAIL,
        kitchen_user_role="kitchen",
    )


def main() -> int:
    if _is_refused_environment():
        raise SystemExit("Refusing to seed outside the isolated local E2E database pair.")
    result = _seed()
    print(
        {
            "tenant_id": result.tenant_id,
            "site_id": result.site_id,
            "main_db_path": result.main_db_path,
            "builder_db_path": result.builder_db_path,
            "builder_menu_id": result.builder_menu_id,
            "year": result.year,
            "week": result.week,
            "service_date": result.service_date,
            "department_count": result.department_count,
            "option_count": result.option_count,
            "menu_choice_counts": result.menu_choice_counts,
            "kitchen_user_email": result.kitchen_user_email,
            "kitchen_user_role": result.kitchen_user_role,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())