from __future__ import annotations

"""Seed department service addon bindings for an existing site.

Safe behavior:
- Never creates sites.
- No deletes.
- No schema changes.
- Idempotent upsert of department_service_addons.

Usage:
  python scripts/seed_department_service_addons.py --input scripts/ostergarden_department_service_addons.json --dry-run
  python scripts/seed_department_service_addons.py --input scripts/ostergarden_department_service_addons.json
"""

import argparse
import os
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import text

# Ensure workspace imports resolve when called as a script.
sys.path.append(os.getcwd())

from core import create_app
from core.db import get_session


@dataclass
class Summary:
    departments_touched: int = 0
    addon_bindings_created: int = 0
    addon_bindings_updated: int = 0
    addon_bindings_unchanged: int = 0


def _load_json(path: str) -> dict:
    import json

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object")
    return payload


def _is_sqlite(db) -> bool:
    try:
        return db.bind.dialect.name == "sqlite"  # type: ignore[union-attr]
    except Exception:
        try:
            return db.get_bind().dialect.name == "sqlite"
        except Exception:
            return False


def _table_exists(db, table_name: str) -> bool:
    if _is_sqlite(db):
        row = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table_name},
        ).fetchone()
        return row is not None
    row = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name=:t
            LIMIT 1
            """
        ),
        {"t": table_name},
    ).fetchone()
    return row is not None


def _table_has_column(db, table_name: str, column_name: str) -> bool:
    if _is_sqlite(db):
        cols = db.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        return any(str(c[1]) == column_name for c in cols)
    row = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name=:t AND column_name=:c
            LIMIT 1
            """
        ),
        {"t": table_name, "c": column_name},
    ).fetchone()
    return row is not None


def _normalize_name(name: str) -> str:
    return " ".join(str(name or "").strip().split())


def _normalize_note(note: str | None) -> str:
    return str(note or "").strip()


def _validate_payload(payload: dict) -> tuple[str, list[dict]]:
    site_name = _normalize_name(str(payload.get("site_name") or ""))
    if not site_name:
        raise ValueError("payload.site_name is required")

    departments = payload.get("departments")
    if not isinstance(departments, list) or not departments:
        raise ValueError("payload.departments must be a non-empty list")

    out: list[dict] = []
    seen_depts: set[str] = set()
    for dep in departments:
        if not isinstance(dep, dict):
            raise ValueError("each department must be an object")
        dep_name = _normalize_name(str(dep.get("name") or ""))
        if not dep_name:
            raise ValueError("department.name is required")
        if dep_name.lower() in seen_depts:
            raise ValueError(f"duplicate department in payload: {dep_name}")
        seen_depts.add(dep_name.lower())

        addons = dep.get("addons")
        if addons is None:
            addons = []
        if not isinstance(addons, list):
            raise ValueError(f"department.addons must be a list for {dep_name}")

        addon_rows: list[dict] = []
        seen_addons: set[str] = set()
        for addon in addons:
            if not isinstance(addon, dict):
                raise ValueError(f"addon entry must be object for {dep_name}")
            addon_name = _normalize_name(str(addon.get("name") or ""))
            if not addon_name:
                raise ValueError(f"addon.name is required for department {dep_name}")
            if addon_name.lower() in seen_addons:
                raise ValueError(f"duplicate addon '{addon_name}' in department {dep_name}")
            seen_addons.add(addon_name.lower())

            try:
                lunch_count = int(addon.get("lunch_count", 0) or 0)
                dinner_count = int(addon.get("dinner_count", 0) or 0)
            except Exception as exc:
                raise ValueError(f"lunch_count/dinner_count must be integers for {dep_name}/{addon_name}") from exc

            if lunch_count < 0 or dinner_count < 0:
                raise ValueError(f"lunch_count/dinner_count must be >= 0 for {dep_name}/{addon_name}")

            note = _normalize_note(addon.get("note"))
            addon_rows.append(
                {
                    "name": addon_name,
                    "lunch_count": lunch_count,
                    "dinner_count": dinner_count,
                    "note": note,
                }
            )

        out.append({"name": dep_name, "addons": addon_rows})

    return site_name, out


def _resolve_site_id(db, site_name: str) -> str:
    row = db.execute(
        text("SELECT id FROM sites WHERE lower(trim(name)) = lower(trim(:n)) ORDER BY id LIMIT 1"),
        {"n": site_name},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Site '{site_name}' not found. This script never creates sites.")
    return str(row[0])


def _resolve_department_id(db, site_id: str, department_name: str) -> str:
    row = db.execute(
        text(
            """
            SELECT id
            FROM departments
            WHERE site_id=:sid AND lower(trim(name)) = lower(trim(:n))
            LIMIT 1
            """
        ),
        {"sid": site_id, "n": department_name},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Department '{department_name}' not found for site_id={site_id}")
    return str(row[0])


def _resolve_addon_id(db, site_id: str, addon_name: str, has_site_id_col: bool) -> str:
    if has_site_id_col:
        row = db.execute(
            text(
                """
                SELECT id
                FROM service_addons
                WHERE site_id=:sid AND lower(trim(name)) = lower(trim(:n))
                LIMIT 1
                """
            ),
            {"sid": site_id, "n": addon_name},
        ).fetchone()
    else:
        row = db.execute(
            text(
                """
                SELECT id
                FROM service_addons
                WHERE lower(trim(name)) = lower(trim(:n))
                LIMIT 1
                """
            ),
            {"n": addon_name},
        ).fetchone()

    if not row:
        scope_txt = f"site_id={site_id}" if has_site_id_col else "global service_addons"
        raise RuntimeError(f"Service addon '{addon_name}' not found in {scope_txt}")
    return str(row[0])


def _fetch_binding_row(db, department_id: str, addon_id: str):
    return db.execute(
        text(
            """
            SELECT id,
                   lunch_count,
                   dinner_count,
                   COALESCE(note, '') AS note
            FROM department_service_addons
            WHERE department_id=:d AND addon_id=:a
            ORDER BY id
            LIMIT 1
            """
        ),
        {"d": department_id, "a": addon_id},
    ).fetchone()


def _insert_binding(
    db,
    *,
    department_id: str,
    addon_id: str,
    lunch_count: int,
    dinner_count: int,
    note: str,
    has_created_at_col: bool,
    dry_run: bool,
) -> None:
    if dry_run:
        return

    bid = str(uuid.uuid4())
    if has_created_at_col:
        db.execute(
            text(
                """
                INSERT INTO department_service_addons(
                    id, department_id, addon_id, lunch_count, dinner_count, note, created_at
                )
                VALUES(:id, :d, :a, :l, :dn, :n, CURRENT_TIMESTAMP)
                """
            ),
            {"id": bid, "d": department_id, "a": addon_id, "l": lunch_count, "dn": dinner_count, "n": note},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO department_service_addons(
                    id, department_id, addon_id, lunch_count, dinner_count, note
                )
                VALUES(:id, :d, :a, :l, :dn, :n)
                """
            ),
            {"id": bid, "d": department_id, "a": addon_id, "l": lunch_count, "dn": dinner_count, "n": note},
        )


def _update_binding(
    db,
    *,
    binding_id: str,
    lunch_count: int,
    dinner_count: int,
    note: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return

    db.execute(
        text(
            """
            UPDATE department_service_addons
            SET lunch_count=:l,
                dinner_count=:dn,
                note=:n
            WHERE id=:id
            """
        ),
        {"id": binding_id, "l": lunch_count, "dn": dinner_count, "n": note},
    )


def run(input_path: str, dry_run: bool) -> int:
    payload = _load_json(input_path)
    site_name, departments = _validate_payload(payload)

    app = create_app()
    summary = Summary()

    with app.app_context():
        db = get_session()
        try:
            # Safety: require existing tables; never create/alter schema in this script.
            for table_name in ("sites", "departments", "service_addons", "department_service_addons"):
                if not _table_exists(db, table_name):
                    raise RuntimeError(f"Required table '{table_name}' not found")

            site_id = _resolve_site_id(db, site_name)
            has_service_addons_site_id = _table_has_column(db, "service_addons", "site_id")
            has_dsa_created_at = _table_has_column(db, "department_service_addons", "created_at")

            touched_departments: set[str] = set()

            for dep in departments:
                dep_name = dep["name"]
                department_id = _resolve_department_id(db, site_id=site_id, department_name=dep_name)

                if dep["addons"]:
                    touched_departments.add(dep_name.lower())

                for addon in dep["addons"]:
                    addon_name = addon["name"]
                    addon_id = _resolve_addon_id(
                        db,
                        site_id=site_id,
                        addon_name=addon_name,
                        has_site_id_col=has_service_addons_site_id,
                    )

                    lunch_count = int(addon["lunch_count"])
                    dinner_count = int(addon["dinner_count"])
                    note = _normalize_note(addon["note"])

                    existing = _fetch_binding_row(db, department_id=department_id, addon_id=addon_id)
                    if not existing:
                        _insert_binding(
                            db,
                            department_id=department_id,
                            addon_id=addon_id,
                            lunch_count=lunch_count,
                            dinner_count=dinner_count,
                            note=note,
                            has_created_at_col=has_dsa_created_at,
                            dry_run=dry_run,
                        )
                        summary.addon_bindings_created += 1
                        continue

                    existing_id = str(existing[0])
                    old_lunch = int(existing[1] or 0) if existing[1] is not None else 0
                    old_dinner = int(existing[2] or 0) if existing[2] is not None else 0
                    old_note = _normalize_note(existing[3])

                    if old_lunch == lunch_count and old_dinner == dinner_count and old_note == note:
                        summary.addon_bindings_unchanged += 1
                        continue

                    _update_binding(
                        db,
                        binding_id=existing_id,
                        lunch_count=lunch_count,
                        dinner_count=dinner_count,
                        note=note,
                        dry_run=dry_run,
                    )
                    summary.addon_bindings_updated += 1

            summary.departments_touched = len(touched_departments)

            if dry_run:
                db.rollback()
            else:
                db.commit()

            print("=== Department service addon seed summary ===")
            print(f"site: {site_name}")
            print(f"dry_run: {str(dry_run).lower()}")
            print("")
            print("bindings:")
            print(f"  departments_touched: {summary.departments_touched}")
            print(f"  addon_bindings_created: {summary.addon_bindings_created}")
            print(f"  addon_bindings_updated: {summary.addon_bindings_updated}")
            print(f"  addon_bindings_unchanged: {summary.addon_bindings_unchanged}")
            return 0
        except Exception as exc:
            db.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            db.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed department service addon bindings for an existing site")
    parser.add_argument("--input", required=True, help="Path to JSON input file")
    parser.add_argument("--dry-run", action="store_true", help="Plan and validate only; no changes committed")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    raise SystemExit(run(input_path=args.input, dry_run=bool(args.dry_run)))
