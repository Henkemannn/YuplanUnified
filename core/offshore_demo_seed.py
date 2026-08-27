from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from flask import Flask, current_app
from sqlalchemy import text

from core.admin_user_repo import AdminUserRepo
from core.builder.library_scope import ActorContext
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_import import import_menu_result_to_builder_canonical
from core.commun_builder_publication import CommunBuilderPublicationRepository
from core.commun_builder_publication import CommunBuilderPublicationService
from core.builder_api import _build_import_review_drafts, _publish_review_drafts
from core.builder_sqlite import (
    SQLiteComponentAliasRepository,
    SQLiteComponentRepository,
    SQLiteCompositionAliasRepository,
    SQLiteCompositionRepository,
    SQLiteMenuRepository,
    initialize_builder_sqlite,
)
from core.db import get_new_session, get_session
from core.offshore_demo_menu_seed import build_demo_menu_import_result
from core.offshore_demo_menu_seed import demo_menu_csv_path
from core.menu_service import MenuServiceDB
from core.week_key import week_key_from_date
from modules.offshore2.menu_context import _service as menu_context_service
from modules.offshore2.models import OffshoreWorkMenuDecision
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
DEMO_BUILDER_ADMIN_EMAIL = "demo.offshore.admin@example.local"
DEMO_BUILDER_ADMIN_USERNAME = DEMO_BUILDER_ADMIN_EMAIL
DEMO_BUILDER_ADMIN_FULL_NAME = "Demo Offshore Admin"
DEMO_BUILDER_ADMIN_PASSWORD = "demo-offshore-admin-password"
DEMO_WEEK_KEY = "demo-offshore-week"
DEMO_MENU_TRACK_VISIBILITY_JSON = json.dumps(
    {
        "primary": [
            {"key": "koett", "label": "Kött"},
            {"key": "fisk", "label": "Fisk"},
        ],
        "secondary": [
            {"key": "soppa", "label": "Soppa"},
        ],
    },
    ensure_ascii=False,
)


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


def _ensure_demo_builder_principal() -> int:
    db = get_session()
    try:
        row = db.execute(
            text(
                """
                SELECT id, tenant_id, role, email
                FROM users
                WHERE tenant_id = :tenant_id
                  AND role IN ('admin', 'superuser')
                  AND lower(email) = :email
                LIMIT 1
                """
            ),
            {"tenant_id": DEMO_TENANT_ID, "email": DEMO_BUILDER_ADMIN_EMAIL.lower()},
        ).fetchone()
        if row is not None:
            if int(row.tenant_id) != DEMO_TENANT_ID:
                raise ValueError("demo builder principal belongs to the wrong tenant")
            if str(row.role or "").strip() != "admin":
                raise ValueError("demo builder principal must be an admin")
            return int(row.id)

        repo = AdminUserRepo()
        user_id = repo.create_user(
            tenant_id=DEMO_TENANT_ID,
            username=DEMO_BUILDER_ADMIN_USERNAME,
            email=DEMO_BUILDER_ADMIN_EMAIL,
            password=DEMO_BUILDER_ADMIN_PASSWORD,
            full_name=DEMO_BUILDER_ADMIN_FULL_NAME,
            role="admin",
            is_active=True,
        )
        return int(user_id)
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

    for menu in list(menu_repository.list_all()):
        menu_id = str(getattr(menu, "menu_id", "") or "").strip()
        if not menu_id.startswith("builder-menu-9001-demo-offshore-") and menu_id != DEMO_BUILDER_MENU_ID:
            continue
        try:
            menu_repository.delete(menu_id)
        except Exception:
            pass

    for composition in list(composition_repository.list_by_group("demo-offshore")):
        composition_id = str(getattr(composition, "composition_id", "") or "").strip()
        if not composition_id:
            continue
        composition_alias_repository.delete_for_composition(composition_id)
        try:
            composition_repository.delete(composition_id)
        except Exception:
            pass

    builder_flow = _builder_flow()
    menu_flow = _builder_menu_context_flow()

    for menu in list(menu_flow.list_menus()):
        menu_id = str(getattr(menu, "menu_id", "") or "").strip()
        if not menu_id.startswith("builder-menu-9001-demo-offshore-") and menu_id != DEMO_BUILDER_MENU_ID:
            continue
        try:
            menu_flow._menu_service.delete_menu(menu_id)
        except Exception:
            pass

    for composition in list(builder_flow.list_compositions(group_name="demo-offshore")):
        composition_id = str(getattr(composition, "composition_id", "") or "").strip()
        if not composition_id:
            continue
        try:
            builder_flow._composition_service.delete_composition(composition_id)
        except Exception:
            pass


def _builder_menu_context_flow():
    from core.builder_menu_context_api import _get_menu_context_flow

    return _get_menu_context_flow()


def _builder_flow():
    from core.builder_api import _get_builder_flow

    return _get_builder_flow()


def _demo_builder_actor() -> ActorContext:
    db = get_session()
    try:
        row = db.execute(
            text(
                """
                SELECT id, tenant_id, role
                FROM users
                WHERE tenant_id = :tenant_id
                  AND role IN ('admin', 'superuser')
                  AND lower(email) = :email
                LIMIT 1
                """
            ),
            {"tenant_id": DEMO_TENANT_ID, "email": DEMO_BUILDER_ADMIN_EMAIL.lower()},
        ).fetchone()
    finally:
        db.close()

    if row is None:
        raise ValueError("demo builder principal not found for tenant 9001")

    return ActorContext(
        tenant_id=int(row.tenant_id),
        user_id=int(row.id),
        site_id=DEMO_SITE_ID,
        role=str(row.role or "admin"),
    )


def _ensure_builder_content(*, anchor_day: date, actor: ActorContext):
    import_result = build_demo_menu_import_result(csv_path=demo_menu_csv_path(), anchor_day=anchor_day)
    _materialize_demo_builder_library(import_result, actor=actor)
    return import_menu_result_to_builder_canonical(
        import_result,
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        import_type="menu",
    )


def _materialize_demo_builder_library(import_result, *, actor: ActorContext) -> None:
    lines = [str(item.dish_name or "").strip() for week in import_result.weeks for item in week.items if str(item.dish_name or "").strip()]
    drafts = _build_import_review_drafts(lines, actor=actor)
    selected_items = [
        {
            **draft,
            "selected": True,
            "item_type": "dish" if draft.get("classification") == "importable_dish" else "ignore",
        }
        for draft in drafts
        if draft.get("classification") == "importable_dish"
    ]
    if selected_items:
        _publish_review_drafts(selected_items, actor=actor)


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
            "menu_track_visibility_json": DEMO_MENU_TRACK_VISIBILITY_JSON,
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
            duration_days=7,
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
            duration_days=7,
            description="Demo period template for offshore smoke testing",
            start_weekday=0,
            active=True,
            sort_order=1,
        )

    template_events = period_service.list_template_events(DEMO_TENANT_ID, DEMO_SITE_ID, int(template.id))
    existing_keys = {(str(row.day_offset), str(row.service_code)) for row in template_events}
    template_event_specs = []
    for day_offset in range(7):
        template_event_specs.append((str(day_offset), time(11, 30), "lunch", "Lunch", positions[1].id if day_offset % 2 == 0 else positions[0].id))
        template_event_specs.append((str(day_offset), time(17, 30), "dinner", "Dinner", positions[2].id if day_offset % 2 == 0 else positions[1].id))
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


def _ensure_work_menu_decisions(work_period_id: int) -> int:
    db = get_session()
    try:
        service_events = (
            db.execute(
                text("SELECT id, starts_at, display_name, service_code FROM offshore_service_events WHERE tenant_id = :tenant_id AND site_id = :site_id ORDER BY starts_at ASC, id ASC"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            ).fetchall()
        )
        context_rows = {
            int(row.service_event_id): row
            for row in db.execute(
                text(
                    "SELECT service_event_id, builder_publication_pin_id, builder_publication_year, builder_publication_week "
                    "FROM offshore_service_event_menu_contexts WHERE tenant_id = :tenant_id AND site_id = :site_id AND work_period_id = :work_period_id"
                ),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID, "work_period_id": work_period_id},
            ).fetchall()
        }
        existing = {
            (int(row.service_event_id), str(row.menu_track_key))
            for row in db.execute(
                text("SELECT service_event_id, menu_track_key FROM offshore_work_menu_decisions WHERE tenant_id = :tenant_id AND site_id = :site_id"),
                {"tenant_id": DEMO_TENANT_ID, "site_id": DEMO_SITE_ID},
            ).fetchall()
        }
        created = 0
        for index, event in enumerate(service_events):
            local_index = index % 7
            service_slot = "lunch" if str(event.service_code).lower() == "lunch" or "lunch" in str(event.display_name).lower() else "dinner"
            decision_matrix = [
                ("koett", "use_published", None, None),
                ("fisk", "use_published", None, None),
                ("soppa", "use_free_text", None, f"Demo {service_slot} soppa dag {local_index + 1}"),
                ("vegetariskt", "use_published", None, None),
            ]
            for track_key, decision_type, selected_builder_composition_id, free_text in decision_matrix:
                if (int(event.id), track_key) in existing:
                    continue
                context_row = context_rows.get(int(event.id))
                db.add(
                    OffshoreWorkMenuDecision(
                        tenant_id=DEMO_TENANT_ID,
                        site_id=DEMO_SITE_ID,
                        service_event_id=int(event.id),
                        menu_track_key=track_key,
                        decision_type=decision_type,
                        selected_builder_composition_id=selected_builder_composition_id,
                        free_text=free_text,
                        source_publication_pin_id=str(getattr(context_row, "builder_publication_pin_id", None) or "") or None,
                        source_publication_year=int(getattr(context_row, "builder_publication_year", 0) or 0),
                        source_publication_week=int(getattr(context_row, "builder_publication_week", 0) or 0),
                    )
                )
                created += 1
        db.commit()
        return created
    finally:
        db.close()


def _ensure_prep_tasks(*, actor: ActorContext) -> int:
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
        "Demo Offshore Kött",
        "Demo Offshore Fisk",
        "Demo Offshore Soppa",
        "Demo Offshore Vegetariskt",
    ]
    component_ids = [builder_flow.create_standalone_component(name, actor=actor).component_id for name in component_names]

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
    iso_year, iso_week, *_ = anchor_day.isocalendar()
    _ensure_tenant_and_site()
    _ensure_feature_flags()
    _ensure_demo_builder_principal()
    _require_commun_builder_schema()
    _clear_scoped_offshore_rows()
    _clear_scoped_builder_rows()
    if reset_only:
        return DemoSeedSummary(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            week_key=week_key_from_date(anchor_day),
            menu_id=DEMO_MENU_ID,
            builder_menu_id=DEMO_BUILDER_MENU_ID,
            work_period_id=0,
            service_event_count=0,
            prep_task_count=0,
        )

    demo_actor = _demo_builder_actor()
    outcomes = _ensure_builder_content(anchor_day=anchor_day, actor=demo_actor)
    publication_service = CommunBuilderPublicationService()
    for outcome in outcomes:
        publication_service.publish_week(
            tenant_id=DEMO_TENANT_ID,
            site_id=DEMO_SITE_ID,
            year=int(outcome.year),
            week=int(outcome.week),
            legacy_menu_id=None,
        )

    _, _, work_period_id = _ensure_offshore_domain(anchor_day=anchor_day)
    _ensure_work_menu_decisions(work_period_id)
    prep_task_count = _ensure_prep_tasks(actor=demo_actor)
    service_event_count = len(period_service.list_service_events(DEMO_TENANT_ID, DEMO_SITE_ID, work_period_id))

    first_outcome = outcomes[0] if outcomes else None

    return DemoSeedSummary(
        tenant_id=DEMO_TENANT_ID,
        site_id=DEMO_SITE_ID,
        week_key=week_key_from_date(anchor_day),
        menu_id=str(first_outcome.menu_id if first_outcome is not None else DEMO_MENU_ID),
        builder_menu_id=str(first_outcome.menu_id if first_outcome is not None else DEMO_BUILDER_MENU_ID),
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
