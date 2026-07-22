from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import click
from flask import Flask, current_app
from sqlalchemy import text

from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.builder_sqlite import (
    SQLiteComponentAliasRepository,
    SQLiteComponentRepository,
    SQLiteCompositionAliasRepository,
    SQLiteCompositionRepository,
    SQLiteMenuRepository,
    initialize_builder_sqlite,
)
from core.db import get_new_session, get_session
from core.menu_service import MenuServiceDB
from core.week_key import week_key_from_date
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.periods import _service as period_service
from modules.offshore2.prep_tasks import _service as prep_service
from modules.offshore2.services import _service as offshore_service


DEMO_TENANT_ID = 9001
DEMO_TENANT_NAME = "Demo Offshore"
DEMO_SITE_ID = "demo-offshore"
DEMO_SITE_NAME = "Demo Offshore Site"
DEMO_MENU_ID = "demo_offshore_week_menu"
DEMO_MENU_TITLE = "Demo Offshore Smoke Menu"
DEMO_BUILDER_MENU_ID = "demo_offshore_builder_week_menu"
DEMO_BUILDER_MENU_TITLE = "Demo Offshore Builder Menu"
DEMO_WEEK_KEY = "demo-offshore-week"


@dataclass(frozen=True)
class DemoSeedSummary:
    tenant_id: int
    site_id: str
    week_key: str
    menu_id: str
    builder_menu_id: str
    work_period_id: int
    service_event_count: int
    prep_task_count: int


def _normalize(value: object | None) -> str:
    return str(value or "").strip()


def _table_exists(table_name: str) -> bool:
    db = get_new_session()
    try:
        dialect_name = getattr(getattr(db.bind, "dialect", None), "name", "")
        if dialect_name != "sqlite":
            try:
                row = db.execute(text("SELECT to_regclass(:name)"), {"name": table_name}).fetchone()
                return bool(row and row[0])
            except Exception:
                return True
        row = db.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = :name"),
            {"name": table_name},
        ).fetchone()
        return row is not None
    finally:
        db.close()


def _table_columns(table_name: str) -> set[str]:
    db = get_new_session()
    try:
        rows = db.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        return {str(row[1]) for row in rows}
    finally:
        db.close()


def _current_alembic_version() -> str:
    db = get_new_session()
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        return str(row[0]) if row and row[0] else "unknown"
    except Exception:
        return "unknown"
    finally:
        db.close()


def _require_commun_builder_schema() -> None:
    required_tables = ("commun_builder_menu_links", "commun_builder_publication_pins")
    missing = [table for table in required_tables if not _table_exists(table)]
    if not missing:
        return

    version = _current_alembic_version()
    missing_list = ", ".join(missing)
    raise click.UsageError(
        "Offshore demo seed cannot run because the local database is schema-drifted: "
        f"missing required table(s): {missing_list}. "
        f"The database reports alembic_version={version}. "
        "Repair the local dev database by backing it up, then run: "
        "python -m alembic stamp 0023_scope_service_addons_by_site && python -m alembic upgrade head. "
        "Do not stamp head without upgrading; that leaves the schema incomplete."
    )


def _db_url_looks_local_sqlite(app: Flask) -> bool:
    raw = _normalize(app.config.get("DATABASE_URL"))
    if raw.startswith("sqlite:"):
        return True
    return False


def _environment_allows_seed(app: Flask, *, force: bool) -> bool:
    env_value = _normalize(app.config.get("APP_ENV") or app.config.get("ENV") or app.config.get("FLASK_ENV")).lower()
    if env_value in {"production", "prod", "pilot"}:
        return False
    if bool(app.config.get("TESTING")):
        return True
    if env_value in {"development", "dev", "testing", "test", "local"}:
        return True
    if force:
        return True
    if _db_url_looks_local_sqlite(app):
        return True
    builder_db = _normalize(app.config.get("BUILDER_DB_PATH"))
    return bool(builder_db.lower().endswith(".db"))


def _ensure_tenant_and_site() -> None:
    db = get_session()
    try:
        if db.bind and getattr(db.bind.dialect, "name", "") == "sqlite":
            cols = db.execute(text("PRAGMA table_info('sites')")).fetchall()
            if not any(str(row[1]) == "tenant_id" for row in cols):
                db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
        db.execute(
            text(
                """
                INSERT INTO tenants (id, name, active)
                VALUES (:id, :name, 1)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, active = excluded.active
                """
            ),
            {"id": DEMO_TENANT_ID, "name": DEMO_TENANT_NAME},
        )
        db.execute(
            text(
                """
                INSERT INTO sites (id, name, tenant_id, version)
                VALUES (:id, :name, :tenant_id, 0)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, tenant_id = excluded.tenant_id
                """
            ),
            {"id": DEMO_SITE_ID, "name": DEMO_SITE_NAME, "tenant_id": DEMO_TENANT_ID},
        )
        db.commit()
    finally:
        db.close()


def _ensure_feature_flags() -> None:
    db = get_session()
    try:
        if _table_exists("tenant_feature_flags"):
            tenant_columns = _table_columns("tenant_feature_flags")
            row = db.execute(
                text("SELECT 1 FROM tenant_feature_flags WHERE tenant_id = :tenant_id AND name = :name LIMIT 1"),
                {"tenant_id": DEMO_TENANT_ID, "name": "offshore.v2.enabled"},
            ).fetchone()
            if row is None:
                fields = ["tenant_id", "name", "enabled"]
                values: dict[str, object] = {"tenant_id": DEMO_TENANT_ID, "name": "offshore.v2.enabled", "enabled": 1}
                if "notes" in tenant_columns:
                    fields.append("notes")
                    values["notes"] = "Demo offshore smoke setup"
                if "updated_at" in tenant_columns:
                    fields.append("updated_at")
                field_sql = ", ".join(fields)
                value_sql = ", ".join(f":{field}" for field in fields)
                if "updated_at" in tenant_columns:
                    value_sql = value_sql.replace(":updated_at", "CURRENT_TIMESTAMP")
                    values.pop("updated_at", None)
                db.execute(text(f"INSERT INTO tenant_feature_flags ({field_sql}) VALUES ({value_sql})"), values)
            else:
                assignments = ["enabled = 1"]
                params: dict[str, object] = {"tenant_id": DEMO_TENANT_ID, "name": "offshore.v2.enabled"}
                if "notes" in tenant_columns:
                    assignments.append("notes = :notes")
                    params["notes"] = "Demo offshore smoke setup"
                if "updated_at" in tenant_columns:
                    assignments.append("updated_at = CURRENT_TIMESTAMP")
                db.execute(
                    text(
                        f"UPDATE tenant_feature_flags SET {', '.join(assignments)} WHERE tenant_id = :tenant_id AND name = :name"
                    ),
                    params,
                )
        if _table_exists("site_feature_flags"):
            try:
                row = db.execute(
                    text("SELECT 1 FROM site_feature_flags WHERE site_id = :site_id AND name = :name LIMIT 1"),
                    {"site_id": DEMO_SITE_ID, "name": "offshore.v2.enabled"},
                ).fetchone()
                if row is None:
                    db.execute(
                        text("INSERT INTO site_feature_flags (site_id, name, enabled) VALUES (:site_id, :name, 1)"),
                        {"site_id": DEMO_SITE_ID, "name": "offshore.v2.enabled"},
                    )
                else:
                    db.execute(
                        text("UPDATE site_feature_flags SET enabled = 1 WHERE site_id = :site_id AND name = :name"),
                        {"site_id": DEMO_SITE_ID, "name": "offshore.v2.enabled"},
                    )
            except Exception:
                pass
        db.commit()
    finally:
        db.close()


def _clear_scoped_offshore_rows() -> None:
    db = get_session()
    try:
        demo_menu_rows = db.execute(
            text("SELECT legacy_menu_id FROM commun_builder_menu_links WHERE tenant_id = :tenant_id AND site_id = :site_id"),
            {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
        ).fetchall()
        for row in demo_menu_rows:
            menu_id = str(row[0])
            if menu_id.lower() in {"none", "null", ""}:
                continue
            db.execute(text("DELETE FROM menu_variants WHERE menu_id = :menu_id"), {"menu_id": menu_id})
            db.execute(text("DELETE FROM menus WHERE id = :menu_id"), {"menu_id": menu_id})

        if _table_exists("commun_builder_menu_links"):
            db.execute(
                text("DELETE FROM commun_builder_menu_links WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("commun_builder_publication_pins"):
            db.execute(
                text("DELETE FROM commun_builder_publication_pins WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_service_event_menu_contexts"):
            db.execute(
                text("DELETE FROM offshore_service_event_menu_contexts WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_prep_tasks"):
            db.execute(
                text("DELETE FROM offshore_prep_tasks WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_service_events"):
            db.execute(
                text("DELETE FROM offshore_service_events WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_work_periods"):
            db.execute(
                text("DELETE FROM offshore_work_periods WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_period_template_events"):
            db.execute(
                text("DELETE FROM offshore_period_template_events WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_period_templates"):
            db.execute(
                text("DELETE FROM offshore_period_templates WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_menu_cycle_slots"):
            db.execute(
                text("DELETE FROM offshore_menu_cycle_slots WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_menu_cycles"):
            db.execute(
                text("DELETE FROM offshore_menu_cycles WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_work_positions"):
            db.execute(
                text("DELETE FROM offshore_work_positions WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        if _table_exists("offshore_installation_settings"):
            db.execute(
                text("DELETE FROM offshore_installation_settings WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            )
        db.commit()
    finally:
        db.close()


def _clear_scoped_builder_rows() -> None:
    builder_db_path = _normalize(current_app.config.get("BUILDER_DB_PATH"))
    if not builder_db_path:
        return

    db_path = initialize_builder_sqlite(builder_db_path)
    menu_repository = SQLiteMenuRepository(db_path=db_path)
    composition_repository = SQLiteCompositionRepository(db_path=db_path)
    composition_alias_repository = SQLiteCompositionAliasRepository(db_path=db_path)
    component_repository = SQLiteComponentRepository(db_path=db_path)
    component_alias_repository = SQLiteComponentAliasRepository(db_path=db_path)

    menu_id = DEMO_BUILDER_MENU_ID
    if menu_repository.get(menu_id) is not None:
        try:
            menu_repository.delete(menu_id)
        except Exception:
            pass

    for composition_id in ("demo_offshore_lunch_plate", "demo_offshore_dinner_plate"):
        if composition_repository.get(composition_id) is None:
            continue
        composition_alias_repository.delete_for_composition(composition_id)
        try:
            composition_repository.delete(composition_id)
        except Exception:
            pass

    demo_component_names = {
        "Demo Offshore Fish",
        "Demo Offshore Root Vegetables",
        "Demo Offshore Herb Sauce",
        "Demo Offshore Green Prep",
    }
    for component in component_repository.list_all():
        if str(component.canonical_name or "") not in demo_component_names:
            continue
        component_id = str(component.component_id)
        component_alias_repository.delete_for_component(component_id)
        try:
            component_repository.delete(component_id)
        except Exception:
            pass

    builder_flow = _builder_flow()
    menu_flow = _builder_menu_context_flow()

    try:
        menu_flow._menu_service.delete_menu(DEMO_BUILDER_MENU_ID)
    except Exception:
        pass

    for composition_id in ("demo_offshore_lunch_plate", "demo_offshore_dinner_plate"):
        try:
            builder_flow._composition_service.delete_composition(composition_id)
        except Exception:
            pass

    demo_component_names = {
        "Demo Offshore Fish",
        "Demo Offshore Root Vegetables",
        "Demo Offshore Herb Sauce",
        "Demo Offshore Green Prep",
    }
    for component in list(builder_flow.list_library_components()):
        component_name = str(getattr(component, "canonical_name", "") or "").strip()
        if component_name not in demo_component_names:
            continue
        try:
            builder_flow._component_alias_repository.delete_for_component(str(component.component_id))
        except Exception:
            pass
        try:
            builder_flow._component_service.delete_component(str(component.component_id))
        except Exception:
            pass


def _builder_menu_context_flow():
    from core.builder_menu_context_api import _get_menu_context_flow

    return _get_menu_context_flow()


def _builder_flow():
    from core.builder_api import _get_builder_flow

    return _get_builder_flow()


def _ensure_builder_content(*, week_key: str) -> dict[str, str]:
    builder_flow = _builder_flow()
    menu_flow = _builder_menu_context_flow()

    component_names = [
        "Demo Offshore Fish",
        "Demo Offshore Root Vegetables",
        "Demo Offshore Herb Sauce",
        "Demo Offshore Green Prep",
    ]
    components = {name: builder_flow.create_standalone_component(name).component_id for name in component_names}

    lunch_composition = builder_flow._composition_repository.get("demo_offshore_lunch_plate")
    if lunch_composition is None:
        lunch_composition = builder_flow.create_composition(
            "demo_offshore_lunch_plate",
            "Demo Offshore Lunch Plate",
            library_group="demo-offshore",
        )
    else:
        lunch_composition = builder_flow._composition_service.update_composition_metadata(
            "demo_offshore_lunch_plate",
            composition_name="Demo Offshore Lunch Plate",
            library_group="demo-offshore",
        )

    dinner_composition = builder_flow._composition_repository.get("demo_offshore_dinner_plate")
    if dinner_composition is None:
        dinner_composition = builder_flow.create_composition(
            "demo_offshore_dinner_plate",
            "Demo Offshore Dinner Plate",
            library_group="demo-offshore",
        )
    else:
        dinner_composition = builder_flow._composition_service.update_composition_metadata(
            "demo_offshore_dinner_plate",
            composition_name="Demo Offshore Dinner Plate",
            library_group="demo-offshore",
        )

    for composition_id, required_names in {
        lunch_composition.composition_id: ["Demo Offshore Fish", "Demo Offshore Herb Sauce"],
        dinner_composition.composition_id: ["Demo Offshore Root Vegetables", "Demo Offshore Green Prep"],
    }.items():
        composition = builder_flow._composition_repository.get(composition_id)
        existing_ids = {item.component_id for item in list(composition.components)} if composition else set()
        for name in required_names:
            component_id = components[name]
            if component_id not in existing_ids:
                builder_flow._composition_service.add_component_to_composition(
                    composition_id,
                    component_id,
                    component_name=name,
                    role="component",
                )

    menu_id = DEMO_BUILDER_MENU_ID
    try:
        menu_flow._menu_service.delete_menu(menu_id)
    except Exception:
        pass
    menu_flow.create_menu(
        menu_id=menu_id,
        site_id=DEMO_SITE_ID,
        week_key=week_key,
        title=DEMO_BUILDER_MENU_TITLE,
        version=1,
        status="draft",
    )
    menu_flow.add_composition_menu_row(menu_id=menu_id, day="monday", meal_slot="lunch", composition_id="demo_offshore_lunch_plate", menu_detail_id="demo_offshore_week_menu_row_1", sort_order=1)
    menu_flow.add_composition_menu_row(menu_id=menu_id, day="tuesday", meal_slot="lunch", composition_id="demo_offshore_dinner_plate", menu_detail_id="demo_offshore_week_menu_row_2", sort_order=2)
    menu_flow.add_composition_menu_row(menu_id=menu_id, day="wednesday", meal_slot="dinner", composition_id="demo_offshore_lunch_plate", menu_detail_id="demo_offshore_week_menu_row_3", sort_order=3)

    return {
        "menu_id": menu_id,
        "lunch_composition_id": "demo_offshore_lunch_plate",
        "dinner_composition_id": "demo_offshore_dinner_plate",
    }


def _ensure_legacy_menu_and_publication(builder_menu_id: str, *, year: int, week: int) -> int:
    legacy_menu_service = MenuServiceDB()
    legacy_menu = legacy_menu_service.create_or_get_menu(tenant_id=DEMO_TENANT_ID, site_id=DEMO_SITE_ID, week=week, year=year)
    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET site_id = :site_id, tenant_id = :tenant_id, status = 'published' WHERE id = :menu_id"),
            {"site_id": DEMO_SITE_ID, "tenant_id": DEMO_TENANT_ID, "menu_id": legacy_menu.id},
        )
        db.commit()
    finally:
        db.close()

    link_service = CommunBuilderMenuLinkService()
    link_service.create_or_replace_link(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        year=year,
        week=week,
        builder_menu_id=builder_menu_id,
        legacy_menu_id=int(legacy_menu.id),
        source="pilot",
    )
    CommunBuilderPublicationRepository().upsert_publication(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        year=year,
        week=week,
        legacy_menu_id=int(legacy_menu.id),
        builder_menu_id=builder_menu_id,
        builder_menu_version=1,
        source="pilot",
    )
    return int(legacy_menu.id)


def _next_monday(value: date) -> date:
    return value + timedelta(days=(7 - value.weekday()) % 7)


def _ensure_offshore_domain(*, anchor_day: date) -> tuple[int, int, int]:
    offshore_service.save_installation_settings(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        actor_user_id=None,
        payload={
            "timezone": "Europe/Oslo",
            "default_locale": "sv",
            "default_theme": "system",
            "default_portions": 120,
            "is_active": True,
        },
    )

    positions = []
    for name, position_type in [
        ("Demo Offshore Prep Lead", "lead"),
        ("Demo Offshore Hot Line", "cook"),
        ("Demo Offshore Cold Prep", "other"),
    ]:
        existing = next((row for row in period_service.list_work_positions(DEMO_TENANT_ID, DEMO_SITE_ID) if str(row.name) == name), None)
        if existing is None:
            existing = offshore_service.create_work_position(
                tenant_id=DEMO_TENANT_ID,
                site_id=DEMO_SITE_ID,
                actor_user_id=None,
                payload={"name": name, "position_type": position_type, "description": f"{name} for demo smoke setup"},
            )
        positions.append(existing)

    cycle = next((row for row in period_service.list_menu_cycles(DEMO_TENANT_ID, DEMO_SITE_ID) if str(row.name) == "Demo Offshore Cycle"), None)
    if cycle is None:
        cycle = offshore_service.create_menu_cycle(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            actor_user_id=None,
            payload={"name": "Demo Offshore Cycle", "description": "Smoke cycle", "cycle_length": 4, "is_active": True},
        )
    else:
        cycle = offshore_service.update_menu_cycle(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            cycle_id=int(cycle.id),
            actor_user_id=None,
            payload={"name": "Demo Offshore Cycle", "description": "Smoke cycle", "cycle_length": 4, "is_active": True},
        )

    template = next((row for row in period_service.list_period_templates(DEMO_TENANT_ID, DEMO_SITE_ID) if str(row.name) == "Demo Offshore Week"), None)
    if template is None:
        template = period_service.create_period_template(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            name="Demo Offshore Week",
            duration_days=4,
            description="Demo period template for offshore smoke testing",
            start_weekday=0,
            active=True,
            sort_order=1,
        )
    else:
        template = period_service.update_period_template(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            template_id=int(template.id),
            name="Demo Offshore Week",
            duration_days=4,
            description="Demo period template for offshore smoke testing",
            start_weekday=0,
            active=True,
            sort_order=1,
        )

    template_events = period_service.list_template_events(DEMO_TENANT_ID, DEMO_SITE_ID, int(template.id))
    existing_keys = {(int(row.day_offset), str(row.service_code)) for row in template_events}
    template_event_specs = [
        (1, time(7, 0), "prep_breakfast", "Breakfast prep", positions[0].id),
        (1, time(11, 30), "prep_lunch", "Lunch prep", positions[1].id),
        (2, time(7, 0), "prep_breakfast", "Breakfast prep", positions[0].id),
        (2, time(11, 30), "prep_lunch", "Lunch prep", positions[1].id),
        (3, time(7, 0), "prep_breakfast", "Breakfast prep", positions[0].id),
        (3, time(11, 30), "prep_lunch", "Lunch prep", positions[2].id),
    ]
    for day_offset, local_time, service_code, display_name, work_position_id in template_event_specs:
        if (day_offset, service_code) in existing_keys:
            continue
        period_service.add_template_event(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            template_id=int(template.id),
            day_offset=day_offset,
            local_time=local_time,
            service_code=service_code,
            display_name=display_name,
            work_position_id=int(work_position_id),
            default_portions=40,
            notes=f"{display_name} for demo smoke setup",
            active=True,
        )

    starts_at = datetime.combine(anchor_day, time(8, 0), tzinfo=ZoneInfo("Europe/Oslo"))
    generation = period_service.create_work_period_from_template(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        period_template_id=int(template.id),
        starts_at=starts_at,
        name="Demo Offshore Smoke Period",
        menu_cycle_id=int(cycle.id),
        notes="Generated by offshore demo smoke seed",
    )

    return int(cycle.id), int(template.id), int(generation.work_period.id)


def _ensure_prep_tasks() -> int:
    db = get_session()
    try:
        service_events = (
            db.execute(
                text("SELECT id, starts_at, display_name, service_code, work_position_id FROM offshore_service_events WHERE tenant_id = :tenant_id AND site_id = :site_id ORDER BY starts_at ASC, id ASC"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            ).fetchall()
        )
    finally:
        db.close()

    builder_flow = _builder_flow()
    component_names = [
        "Demo Offshore Fish",
        "Demo Offshore Root Vegetables",
        "Demo Offshore Herb Sauce",
        "Demo Offshore Green Prep",
    ]
    component_ids = [builder_flow.create_standalone_component(name).component_id for name in component_names]

    created_count = 0
    for index, event in enumerate(service_events):
        component_id = component_ids[index % len(component_ids)]
        existing = prep_service.list_tasks_for_service_event(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            service_event_id=int(event[0]),
            role="admin",
            user_id=None,
        )
        if existing:
            continue
        task = prep_service.create_task(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            service_event_id=int(event[0]),
            actor_user_id=None,
            role="admin",
            payload={
                "title": f"Demo prep {index + 1}",
                "instructions": f"Prep {event[3]} for demo smoke testing.",
                "planned_date": datetime.fromisoformat(str(event[1])).astimezone(ZoneInfo("Europe/Oslo")).date().isoformat(),
                "planned_time": "06:30",
                "builder_component_id": component_id,
                "work_position_id": event[4],
                "sort_order": index + 1,
            },
        )
        if index == 1:
            prep_service.transition_task(
                tenant_id=DEMO_TENANT_ID,
                site_id=DEMO_SITE_ID,
                task_id=int(task.id),
                actor_user_id=None,
                role="admin",
                new_status="in_progress",
            )
        elif index == 2:
            prep_service.transition_task(
                tenant_id=DEMO_TENANT_ID,
                site_id=DEMO_SITE_ID,
                task_id=int(task.id),
                actor_user_id=None,
                role="admin",
                new_status="completed",
            )
        created_count += 1
    return created_count


def seed_demo(*, reset_only: bool = False) -> DemoSeedSummary:
    anchor_day = _next_monday(datetime.now(UTC).astimezone(ZoneInfo("Europe/Oslo")).date())
    week_key = week_key_from_date(anchor_day)
    iso_year, iso_week, *_ = anchor_day.isocalendar()
    _ensure_tenant_and_site()
    _ensure_feature_flags()
    _require_commun_builder_schema()
    if reset_only:
        _clear_scoped_offshore_rows()
        _clear_scoped_builder_rows()
        return DemoSeedSummary(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            week_key=week_key,
            menu_id=DEMO_MENU_ID,
            builder_menu_id=DEMO_BUILDER_MENU_ID,
            work_period_id=0,
            service_event_count=0,
            prep_task_count=0,
        )

    _ensure_builder_content(week_key=week_key)
    builder_menu_id = DEMO_BUILDER_MENU_ID
    menu_flow = _builder_menu_context_flow()
    if menu_flow._menu_service.get_menu(builder_menu_id) is None:
        menu_flow.create_menu(
            menu_id=builder_menu_id,
            site_id=DEMO_SITE_ID,
            week_key=week_key,
            title=DEMO_BUILDER_MENU_TITLE,
            version=1,
            status="draft",
        )
    legacy_menu_id = _ensure_legacy_menu_and_publication(builder_menu_id, year=int(iso_year), week=int(iso_week))

    _, _, work_period_id = _ensure_offshore_domain(anchor_day=anchor_day)
    prep_task_count = _ensure_prep_tasks()
    service_event_count = len(period_service.list_service_events(DEMO_TENANT_ID, DEMO_SITE_ID, work_period_id))

    return DemoSeedSummary(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        week_key=week_key,
        menu_id=str(legacy_menu_id),
        builder_menu_id=builder_menu_id,
        work_period_id=work_period_id,
        service_event_count=service_event_count,
        prep_task_count=prep_task_count,
    )


def register_offshore_demo_seed_cli(app: Flask) -> None:
    if getattr(app, "_offshore_demo_seed_cli_registered", False):
        return

    @app.cli.command("offshore-demo-seed")
    @click.option("--force", is_flag=True, help="Allow the seed to run outside development/testing when the database is still local.")
    @click.option("--reset", is_flag=True, help="Clear only the scoped demo rows and exit.")
    def offshore_demo_seed(force: bool, reset: bool) -> None:
        """Seed the Offshore smoke demo data set."""
        if not _environment_allows_seed(current_app, force=force):
            raise click.UsageError("refusing to seed outside development/testing or a local sqlite setup")
        summary = seed_demo(reset_only=reset)
        if reset:
            click.echo(f"reset demo tenant={summary.tenant_id} site={summary.site_id}")
            return
        click.echo(
            f"seeded tenant={summary.tenant_id} site={summary.site_id} menu={summary.menu_id} "
            f"builder_menu={summary.builder_menu_id} work_period={summary.work_period_id} "
            f"service_events={summary.service_event_count} prep_tasks={summary.prep_task_count}"
        )

    app._offshore_demo_seed_cli_registered = True
