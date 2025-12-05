"""Seed script for Demo Kommun core flow (idempotent).

Usage:
  python -m scripts.seed_demo_kommun_core

Behavior:
- Ensures tenant 1 exists and is named "Demo Kommun" (safe upsert across sqlite/postgres).
- Recreates a site named "Midsommargården" with two departments: "Avd 1" and "Avd 2".
- Sets resident count mode to fixed with reasonable counts.
- Ensures diet types (Gluten, Laktos, Vegetarisk) exist and links department diet defaults.
- Creates a full published menu for a canonical week/year (lunch + dinner set for all 7 days, alt2 on a couple of days).
- Seeds weekview alt2 flags and residents counts for the same departments and week.

Idempotent: re-running resets the specific demo site/departments/menu for the chosen week.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.admin_repo import SitesRepo, DepartmentsRepo, _is_sqlite
from core.weekview.repo import WeekviewRepo
from core.menu_service import MenuServiceDB
from core.models import Dish, Tenant

TENANT_ID = 1
TENANT_NAME = "Demo Kommun"
SITE_NAME = "Midsommargården"
DEPARTMENTS = [
    {"name": "Avd 1", "resident_count_mode": "fixed", "resident_count_fixed": 16},
    {"name": "Avd 2", "resident_count_mode": "fixed", "resident_count_fixed": 14},
]
# Use canonical values that align with portal/weekview tests
YEAR = 2025
WEEK = 47

DIET_TYPES = ["Gluten", "Laktos", "Vegetarisk"]
DIET_DEFAULTS = {
    "Avd 1": {"Gluten": 2, "Laktos": 1, "Vegetarisk": 1},
    "Avd 2": {"Gluten": 1, "Vegetarisk": 2},
}
# Alt2 lunch enabled weekdays (Tue, Thu)
ALT2_DAYS = [2, 4]

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Created:
    site_id: str
    department_ids: dict[str, str]


def _ensure_engine() -> None:
    url = os.getenv("DATABASE_URL")
    if url:
        init_engine(url)
    else:
        # Fall back to app factory (dev/test convenience)
        create_app()


def _ensure_tenant() -> int:
    db = get_session()
    try:
        # Try to ensure a row with id=TENANT_ID exists and is named TENANT_NAME
        if _is_sqlite(db):
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS tenants(
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
            """))
            # Insert row id=1 if missing
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:i, :n, 1)"), {"i": TENANT_ID, "n": TENANT_NAME})
            # Ensure name matches (reset to Demo Kommun for demo tenant)
            db.execute(text("UPDATE tenants SET name=:n, active=1 WHERE id=:i"), {"i": TENANT_ID, "n": TENANT_NAME})
        else:
            # Postgres upsert by id
            db.execute(text(
                """
                INSERT INTO tenants(id, name, active)
                VALUES (:i, :n, TRUE)
                ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, active=TRUE
                """
            ), {"i": TENANT_ID, "n": TENANT_NAME})
        db.commit()
        return TENANT_ID
    finally:
        db.close()


def _reset_site(site_name: str) -> None:
    """Delete existing site with this name and its departments' related demo data for the target week."""
    sites_repo = SitesRepo()
    depts_repo = DepartmentsRepo()
    db = get_session()
    try:
        # SQLite safety: ensure sites table has expected columns (version, notes, updated_at)
        if _is_sqlite(db):
            # Create table if missing
            db.execute(text(
                """
                CREATE TABLE IF NOT EXISTS sites (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NULL,
                    updated_at TEXT
                )
                """
            ))
            # Add missing columns if legacy table exists
            def _has_col(table: str, col: str) -> bool:
                rows = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
                return any(str(r[1]) == col for r in rows)
            if not _has_col("sites", "version"):
                db.execute(text("ALTER TABLE sites ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
            if not _has_col("sites", "notes"):
                db.execute(text("ALTER TABLE sites ADD COLUMN notes TEXT"))
            if not _has_col("sites", "updated_at"):
                db.execute(text("ALTER TABLE sites ADD COLUMN updated_at TEXT"))
            db.commit()
        existing_sites = sites_repo.list_sites()
        site = next((s for s in existing_sites if s.get("name") == site_name), None)
        if not site:
            return
        site_id = site["id"]
        # Ensure departments table expected columns before listing
        if _is_sqlite(db):
            db.execute(text(
                """
                CREATE TABLE IF NOT EXISTS departments (
                    id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    resident_count_mode TEXT NOT NULL,
                    resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                )
                """
            ))
            def _has_col_dep(col: str) -> bool:
                rows = db.execute(text("PRAGMA table_info('departments')")).fetchall()
                return any(str(r[1]) == col for r in rows)
            if not _has_col_dep("resident_count_mode"):
                db.execute(text("ALTER TABLE departments ADD COLUMN resident_count_mode TEXT NOT NULL DEFAULT 'fixed'"))
            if not _has_col_dep("resident_count_fixed"):
                db.execute(text("ALTER TABLE departments ADD COLUMN resident_count_fixed INTEGER NOT NULL DEFAULT 0"))
            if not _has_col_dep("notes"):
                db.execute(text("ALTER TABLE departments ADD COLUMN notes TEXT"))
            if not _has_col_dep("version"):
                db.execute(text("ALTER TABLE departments ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
            if not _has_col_dep("updated_at"):
                db.execute(text("ALTER TABLE departments ADD COLUMN updated_at TEXT"))
            db.commit()
        departments = depts_repo.list_for_site(site_id)

        def _table_exists(table: str) -> bool:
            try:
                if _is_sqlite(db):
                    rows = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
                    return len(rows) > 0
                row = db.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).fetchone()
                return bool(row and row[0])
            except Exception:
                return False
        # Clean related data per department and target week
        for d in departments:
            dept_id = d["id"]
            # Weekview aggregates for target year/week and demo tenant (if tables exist)
            if _table_exists("weekview_registrations"):
                db.execute(text("DELETE FROM weekview_registrations WHERE tenant_id=:t AND department_id=:d AND year=:y AND week=:w"), {"t": str(TENANT_ID), "d": dept_id, "y": YEAR, "w": WEEK})
            if _table_exists("weekview_residents_count"):
                db.execute(text("DELETE FROM weekview_residents_count WHERE tenant_id=:t AND department_id=:d AND year=:y AND week=:w"), {"t": str(TENANT_ID), "d": dept_id, "y": YEAR, "w": WEEK})
            if _table_exists("weekview_alt2_flags"):
                db.execute(text("DELETE FROM weekview_alt2_flags WHERE tenant_id=:t AND department_id=:d AND year=:y AND week=:w"), {"t": str(TENANT_ID), "d": dept_id, "y": YEAR, "w": WEEK})
            # Department diet defaults
            db.execute(text("DELETE FROM department_diet_defaults WHERE department_id=:d"), {"d": dept_id})
            # Alt2 choice storage
            db.execute(text("DELETE FROM alt2_flags WHERE department_id=:d AND week=:w"), {"d": dept_id, "w": WEEK})
            # Remove department itself
            db.execute(text("DELETE FROM departments WHERE id=:id"), {"id": dept_id})
        # Remove site
        db.execute(text("DELETE FROM sites WHERE id=:id"), {"id": site_id})
        # Remove menu + variants for this week/year tenant (clean slate)
        db.execute(text("DELETE FROM menu_variants WHERE menu_id IN (SELECT id FROM menus WHERE tenant_id=:t AND week=:w AND year=:y)"), {"t": TENANT_ID, "w": WEEK, "y": YEAR})
        db.execute(text("DELETE FROM menus WHERE tenant_id=:t AND week=:w AND year=:y"), {"t": TENANT_ID, "w": WEEK, "y": YEAR})
        # Remove demo dishes we previously created (by name prefix)
        db.execute(text("DELETE FROM dishes WHERE tenant_id=:t AND name LIKE 'Demo %'"), {"t": TENANT_ID})
        db.commit()
    finally:
        db.close()


def _create_site_and_departments() -> Created:
    sites_repo = SitesRepo()
    depts_repo = DepartmentsRepo()
    # Ensure departments table has expected columns on SQLite (for legacy local DBs)
    db = get_session()
    try:
        if _is_sqlite(db):
            db.execute(text(
                """
                CREATE TABLE IF NOT EXISTS departments (
                    id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    resident_count_mode TEXT NOT NULL,
                    resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                )
                """
            ))
            def _has_col(table: str, col: str) -> bool:
                rows = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
                return any(str(r[1]) == col for r in rows)
            if not _has_col("departments", "resident_count_mode"):
                db.execute(text("ALTER TABLE departments ADD COLUMN resident_count_mode TEXT NOT NULL DEFAULT 'fixed'"))
            if not _has_col("departments", "resident_count_fixed"):
                db.execute(text("ALTER TABLE departments ADD COLUMN resident_count_fixed INTEGER NOT NULL DEFAULT 0"))
            if not _has_col("departments", "notes"):
                db.execute(text("ALTER TABLE departments ADD COLUMN notes TEXT"))
            if not _has_col("departments", "version"):
                db.execute(text("ALTER TABLE departments ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
            if not _has_col("departments", "updated_at"):
                db.execute(text("ALTER TABLE departments ADD COLUMN updated_at TEXT"))
            db.commit()
    finally:
        db.close()
    created_site, _ = sites_repo.create_site(SITE_NAME)
    site_id = created_site["id"]
    dept_ids: dict[str, str] = {}
    for d in DEPARTMENTS:
        created, _ = depts_repo.create_department(
            site_id,
            d["name"],
            d.get("resident_count_mode", "fixed"),
            int(d.get("resident_count_fixed", 0)),
        )
        dept_ids[d["name"]] = created["id"]
    return Created(site_id=site_id, department_ids=dept_ids)


def _ensure_diet_types() -> None:
    """Ensure diet_types rows exist with ids matching names (cross-dialect).

    Note: Admin V2 uses a new table diet_types(id TEXT, name TEXT, ...), while
    older UI/services may still reference dietary_types. For the purposes of
    department_diet_defaults FKs and weekview defaults, we must ensure
    diet_types contains our canonical names with id==name.
    """
    db = get_session()
    try:
        if _is_sqlite(db):
            db.execute(text(
                """
                CREATE TABLE IF NOT EXISTS diet_types (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    premarked INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                )
                """
            ))
            for n in DIET_TYPES:
                db.execute(
                    text("INSERT OR IGNORE INTO diet_types (id, name, premarked) VALUES (:id,:name, 0)"),
                    {"id": n, "name": n},
                )
        else:
            existing_names = {str(r[0]) for r in db.execute(text("SELECT name FROM diet_types")).fetchall()}
            for n in DIET_TYPES:
                if n not in existing_names:
                    db.execute(
                        text(
                            "INSERT INTO diet_types (id, name, premarked) VALUES (:id, :name, FALSE)"
                        ),
                        {"id": n, "name": n},
                    )
        db.commit()
    finally:
        db.close()


def _upsert_diet_defaults(dept_ids: dict[str, str]) -> None:
    depts_repo = DepartmentsRepo()
    # Resolve diet type names to canonical IDs used by department_diet_defaults (Postgres diet_types.id)
    id_by_name: dict[str, str] = {}
    db = get_session()
    try:
        rows = db.execute(text("SELECT id, name FROM diet_types")).fetchall()
        id_by_name = {str(r[1]).strip().lower(): str(r[0]).strip() for r in rows}
    except Exception:
        id_by_name = {}
    finally:
        db.close()
    for dept_name, mapping in DIET_DEFAULTS.items():
        did = dept_ids.get(dept_name)
        if not did:
            continue
        items: list[dict[str, Any]] = []
        for diet, cnt in mapping.items():
            key = str(diet).strip().lower()
            diet_id = id_by_name.get(key, diet)
            items.append({"diet_type_id": diet_id, "default_count": int(cnt)})
        ver = depts_repo.get_version(did) or 0
        depts_repo.upsert_department_diet_defaults(did, ver, items)


def _seed_menu() -> int:
    svc = MenuServiceDB()
    # Remove any previous menu for idempotency is handled in _reset_site
    menu = svc.create_or_get_menu(tenant_id=TENANT_ID, week=WEEK, year=YEAR)
    # Create dishes with clear Demo prefix and set variants
    # Use a separate session for dish inserts
    from core.db import get_new_session

    session = get_new_session()
    try:
        dish_ids: dict[str, int] = {}
        for i, dk in enumerate(DAY_KEYS):
            # Lunch alt1
            d_l = Dish(tenant_id=TENANT_ID, name=f"Demo Lunch {DAY_NAMES[i]}")
            # Dinner alt1
            d_d = Dish(tenant_id=TENANT_ID, name=f"Demo Dinner {DAY_NAMES[i]}")
            session.add_all([d_l, d_d])
            session.flush()
            session.refresh(d_l)
            session.refresh(d_d)
            dish_ids[f"{dk}:lunch:alt1"] = d_l.id  # type: ignore[attr-defined]
            dish_ids[f"{dk}:dinner:alt1"] = d_d.id  # type: ignore[attr-defined]
            # Optional lunch alt2 for ALT2_DAYS
            dow = i + 1
            if dow in ALT2_DAYS:
                d_a2 = Dish(tenant_id=TENANT_ID, name=f"Demo Lunch Alt2 {DAY_NAMES[i]}")
                session.add(d_a2)
                session.flush()
                session.refresh(d_a2)
                dish_ids[f"{dk}:lunch:alt2"] = d_a2.id  # type: ignore[attr-defined]
        session.commit()
        # Set variants in menu
        for i, dk in enumerate(DAY_KEYS):
            svc.set_variant(tenant_id=TENANT_ID, menu_id=menu.id, day=dk, meal="lunch", variant_type="alt1", dish_id=dish_ids[f"{dk}:lunch:alt1"])  # type: ignore[index]
            svc.set_variant(tenant_id=TENANT_ID, menu_id=menu.id, day=dk, meal="dinner", variant_type="alt1", dish_id=dish_ids[f"{dk}:dinner:alt1"])  # type: ignore[index]
            dow = i + 1
            if dow in ALT2_DAYS:
                svc.set_variant(tenant_id=TENANT_ID, menu_id=menu.id, day=dk, meal="lunch", variant_type="alt2", dish_id=dish_ids.get(f"{dk}:lunch:alt2"))
        # Publish for clarity
        svc.publish_menu(tenant_id=TENANT_ID, menu_id=menu.id)
        return int(menu.id)
    finally:
        session.close()


def _seed_weekview_for_departments(site_id: str, dept_ids: dict[str, str]) -> None:
    # On SQLite test/dev, use WeekviewRepo tables; on Postgres staging, use Alt2Repo only
    db = get_session()
    try:
        if _is_sqlite(db):
            repo = WeekviewRepo()
            for dept_name, dept_id in dept_ids.items():
                repo.set_alt2_flags(TENANT_ID, YEAR, WEEK, dept_id, ALT2_DAYS)
                fixed = next((int(d.get("resident_count_fixed", 0)) for d in DEPARTMENTS if d["name"] == dept_name), 0)
                items: list[dict[str, Any]] = []
                for dow in range(1, 8):
                    items.append({"day_of_week": dow, "meal": "lunch", "count": fixed})
                    items.append({"day_of_week": dow, "meal": "dinner", "count": max(fixed - 2, 0)})
                repo.set_residents_counts(TENANT_ID, YEAR, WEEK, dept_id, items)
        else:
            from core.admin_repo import Alt2Repo
            alt2 = Alt2Repo()
            payload: list[dict[str, Any]] = []
            for _, dept_id in dept_ids.items():
                for dow in ALT2_DAYS:
                    payload.append({
                        "site_id": site_id,
                        "department_id": dept_id,
                        "week": WEEK,
                        "weekday": dow,
                        "enabled": True,
                    })
            if payload:
                alt2.bulk_upsert(payload)
    finally:
        db.close()


def run() -> int:
    _ensure_engine()
    _ensure_tenant()
    # Reset any existing demo site/departments for a clean slate
    _reset_site(SITE_NAME)
    # Create site and departments fresh
    created = _create_site_and_departments()
    # Diet types + defaults
    _ensure_diet_types()
    _upsert_diet_defaults(created.department_ids)
    # Menu
    menu_id = _seed_menu()
    # Weekview aggregates
    _seed_weekview_for_departments(created.site_id, created.department_ids)

    print("Seed OK - Demo Kommun core flow ready.")
    print(f"Tenant: id={TENANT_ID}, name={TENANT_NAME}")
    print(f"Site: {SITE_NAME} -> id={created.site_id}")
    print("Departments:")
    for name, did in created.department_ids.items():
        print(f"  - {name}: id={did}")
    print(f"Menu(year={YEAR}, week={WEEK}): id={menu_id} (published)")
    print(f"Alt2 lunch days: {ALT2_DAYS}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
