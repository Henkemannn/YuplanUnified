from __future__ import annotations

"""One-off seed importer for Östergården from structured JSON.

Safe behavior:
- Never creates sites.
- Upserts departments by (site_id, name).
- Upserts dietary types by (site_id, name).
- Upserts department_diet_defaults by (department_id, diet_type_id).
- Idempotent and safe to re-run.
- No deletes in v1.

Usage:
  py -3.12 scripts/seed_ostergarden_from_json.py --input scripts/ostergarden_seed.json --dry-run
  py -3.12 scripts/seed_ostergarden_from_json.py --input scripts/ostergarden_seed.json
"""

import argparse
import os
import sys
from dataclasses import dataclass

from sqlalchemy import text

# Ensure workspace imports resolve when called as a script.
sys.path.append(os.getcwd())

from core import create_app
from core.db import get_session

SITE_NAME_REQUIRED = "Östergården"
IGNORED_DIET_NAMES = {
    "mos",
    "sallad",
    "menyalternativ",
}

DIET_NAME_NORMALIZATION = {
    "tjock flytande": "Flytande",
    "minus fisk": "Ej fisk",
    "minus sill": "Ej sill",
}

DEFAULT_DIET_FAMILY_MAP = {
    "Timbal": "Textur",
    "Grovpaté": "Textur",
    "Flytande": "Textur",
    "Ej fisk": "Allergi / Exkludering",
    "Ej sill": "Allergi / Exkludering",
    "Ej kyckling": "Allergi / Exkludering",
    "Ej lax": "Allergi / Exkludering",
    "Ej ärtsoppa": "Allergi / Exkludering",
    "Ej dillkött": "Allergi / Exkludering",
    "Ej lever": "Allergi / Exkludering",
    "Ej skaldjur": "Allergi / Exkludering",
    "Vegetariskt": "Kostval",
    "Vegan": "Kostval",
    "Vegansk": "Kostval",
    "Energireducerad": "Anpassning",
    "Energiberikad": "Anpassning",
}


@dataclass
class Summary:
    departments_created: int = 0
    departments_updated: int = 0
    departments_unchanged: int = 0
    diets_created: int = 0
    diets_reused: int = 0
    bindings_created: int = 0
    bindings_updated: int = 0
    bindings_unchanged: int = 0
    ignored_diets: int = 0
    diet_family_updates: int = 0


def _normalize_diet_name(name: str) -> str:
    clean = str(name or "").strip()
    if not clean:
        return ""
    return DIET_NAME_NORMALIZATION.get(clean.lower(), clean)


def _canonical_family_name(raw_family: str | None) -> str:
    family = str(raw_family or "").strip()
    if not family:
        return "Övrigt"
    return family


def _build_diet_family_map(payload: dict, departments: list[dict]) -> dict[str, str]:
    out: dict[str, str] = dict(DEFAULT_DIET_FAMILY_MAP)
    declared = payload.get("diet_types")
    if isinstance(declared, list):
        for item in declared:
            if not isinstance(item, dict):
                continue
            nm = _normalize_diet_name(str(item.get("name") or ""))
            if not nm:
                continue
            fam = _canonical_family_name(item.get("diet_family"))
            out[nm] = fam

    # Ensure every referenced diet has a safe family assignment.
    for dep in departments:
        diets = dep.get("clear_special_diets") or {}
        if not isinstance(diets, dict):
            continue
        for diet_name in diets.keys():
            nm = _normalize_diet_name(str(diet_name or ""))
            if not nm:
                continue
            if nm not in out:
                out[nm] = "Övrigt"
    return out


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


def _ensure_department_table_shape(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                site_id TEXT NOT NULL,
                name TEXT NOT NULL,
                resident_count_mode TEXT NOT NULL DEFAULT 'fixed',
                resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                notes TEXT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
            """
        )
    )


def _ensure_dietary_types_table_shape(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS dietary_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NULL,
                site_id TEXT NULL,
                name TEXT NOT NULL,
                diet_family TEXT NOT NULL DEFAULT 'Övrigt',
                default_select INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    )
    cols = {str(r[1]) for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
    if "site_id" not in cols:
        db.execute(text("ALTER TABLE dietary_types ADD COLUMN site_id TEXT"))
    if "diet_family" not in cols:
        db.execute(text("ALTER TABLE dietary_types ADD COLUMN diet_family TEXT"))


def _ensure_defaults_table_shape(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS department_diet_defaults (
                department_id TEXT NOT NULL,
                diet_type_id TEXT NOT NULL,
                default_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (department_id, diet_type_id)
            )
            """
        )
    )


def _resolve_site_context(db, site_name: str) -> tuple[str, int | None]:
    # Resolve site first; tenant_id is best-effort (some schemas may not have the column).
    site_id_row = db.execute(
        text("SELECT id FROM sites WHERE lower(trim(name)) = lower(trim(:n)) ORDER BY id LIMIT 1"),
        {"n": site_name},
    ).fetchone()
    if not site_id_row:
        raise RuntimeError(f"Site '{site_name}' not found. This script never creates sites.")
    site_id = str(site_id_row[0])

    tenant_id: int | None = None
    try:
        row_t = db.execute(text("SELECT tenant_id FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if row_t and row_t[0] is not None:
            tenant_id = int(row_t[0])
    except Exception:
        tenant_id = None

    return site_id, tenant_id


def _get_dept_by_name(db, site_id: str, name: str):
    return db.execute(
        text(
            """
            SELECT id, COALESCE(resident_count_mode, 'fixed') AS resident_count_mode,
                   COALESCE(resident_count_fixed, 0) AS resident_count_fixed,
                   COALESCE(version, 0) AS version
            FROM departments
            WHERE site_id=:s AND lower(trim(name)) = lower(trim(:n))
            LIMIT 1
            """
        ),
        {"s": site_id, "n": name},
    ).fetchone()


def _create_department(db, site_id: str, name: str, resident_count: int, dry_run: bool) -> None:
    if dry_run:
        return
    import uuid

    dept_id = str(uuid.uuid4())
    if _is_sqlite(db):
        db.execute(
            text(
                """
                INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)
                VALUES(:id, :sid, :name, 'fixed', :rc, 0)
                """
            ),
            {"id": dept_id, "sid": site_id, "name": name, "rc": int(resident_count)},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed)
                VALUES(:id, :sid, :name, 'fixed', :rc)
                """
            ),
            {"id": dept_id, "sid": site_id, "name": name, "rc": int(resident_count)},
        )


def _update_department_counts(db, dept_id: str, resident_count: int, dry_run: bool) -> None:
    if dry_run:
        return
    if _is_sqlite(db):
        db.execute(
            text(
                """
                UPDATE departments
                SET resident_count_mode='fixed', resident_count_fixed=:rc,
                    version=COALESCE(version, 0)+1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:id
                """
            ),
            {"id": dept_id, "rc": int(resident_count)},
        )
    else:
        db.execute(
            text(
                """
                UPDATE departments
                SET resident_count_mode='fixed', resident_count_fixed=:rc,
                    version=COALESCE(version, 0)+1,
                    updated_at=now()
                WHERE id=:id
                """
            ),
            {"id": dept_id, "rc": int(resident_count)},
        )


def _resolve_or_create_diet_type_id(
    db,
    site_id: str,
    diet_name: str,
    dry_run: bool,
    summary: Summary,
    diet_family_by_name: dict[str, str],
    known_diet_ids_by_name: dict[str, str],
    site_tenant_id: int | None,
) -> str | None:
    clean = _normalize_diet_name(str(diet_name or ""))
    if not clean:
        return None
    if clean.lower() in IGNORED_DIET_NAMES:
        summary.ignored_diets += 1
        return None
    cache_key = clean.lower()
    diet_family = _canonical_family_name(diet_family_by_name.get(clean) or DEFAULT_DIET_FAMILY_MAP.get(clean) or "Övrigt")

    # For dry-run, reuse pseudo-created diet ids within this run so repeated names
    # across departments count as reused instead of re-created.
    if cache_key in known_diet_ids_by_name:
        summary.diets_reused += 1
        return known_diet_ids_by_name[cache_key]

    row = db.execute(
        text(
            """
            SELECT id, COALESCE(NULLIF(trim(CAST(diet_family AS TEXT)), ''), 'Övrigt') AS diet_family
            FROM dietary_types
            WHERE site_id=:s AND lower(trim(name)) = lower(trim(:n))
            LIMIT 1
            """
        ),
        {"s": site_id, "n": clean},
    ).fetchone()
    if row:
        known_diet_ids_by_name[cache_key] = str(row[0])
        current_family = str(row[1] or "Övrigt")
        if current_family != diet_family:
            summary.diet_family_updates += 1
            if not dry_run:
                db.execute(
                    text("UPDATE dietary_types SET diet_family=:f WHERE id=:id"),
                    {"f": diet_family, "id": row[0]},
                )
        summary.diets_reused += 1
        return str(row[0])

    if dry_run:
        summary.diets_created += 1
        pseudo_id = f"dry-run::{clean}"
        known_diet_ids_by_name[cache_key] = pseudo_id
        return pseudo_id

    if _is_sqlite(db):
        cols = {str(r[1]) for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
        notnull_map = {str(r[1]): int(r[3] or 0) for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
        needs_tenant = "tenant_id" in cols and bool(notnull_map.get("tenant_id", 0))
        if "tenant_id" in cols and (site_tenant_id is not None or needs_tenant):
            if site_tenant_id is None and needs_tenant:
                raise RuntimeError("Could not resolve tenant_id for site; dietary_types.tenant_id is required")
            db.execute(
                text(
                    """
                    INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, default_select)
                    VALUES(:t, :s, :n, :f, 0)
                    """
                ),
                {"t": site_tenant_id, "s": site_id, "n": clean, "f": diet_family},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO dietary_types(site_id, name, diet_family, default_select)
                    VALUES(:s, :n, :f, 0)
                    """
                ),
                {"s": site_id, "n": clean, "f": diet_family},
            )
        created = db.execute(text("SELECT last_insert_rowid()")).fetchone()
        new_id = str(created[0]) if created else ""
    else:
        if site_tenant_id is not None:
            created = db.execute(
                text(
                    """
                    INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, default_select)
                    VALUES(:t, :s, :n, :f, false)
                    RETURNING id
                    """
                ),
                {"t": site_tenant_id, "s": site_id, "n": clean, "f": diet_family},
            ).fetchone()
        else:
            created = db.execute(
                text(
                    """
                    INSERT INTO dietary_types(site_id, name, diet_family, default_select)
                    VALUES(:s, :n, :f, false)
                    RETURNING id
                    """
                ),
                {"s": site_id, "n": clean, "f": diet_family},
            ).fetchone()
        new_id = str(created[0]) if created else ""

    if not new_id:
        raise RuntimeError(f"Could not create diet type id for '{clean}'")

    known_diet_ids_by_name[cache_key] = new_id
    summary.diets_created += 1
    return new_id


def _get_existing_binding_count(db, dept_id: str, diet_type_id: str):
    row = db.execute(
        text(
            """
            SELECT default_count
            FROM department_diet_defaults
            WHERE department_id=:d AND diet_type_id=:t
            LIMIT 1
            """
        ),
        {"d": dept_id, "t": str(diet_type_id)},
    ).fetchone()
    if not row:
        return None
    return int(row[0] or 0)


def _upsert_binding(db, dept_id: str, diet_type_id: str, count: int, dry_run: bool) -> None:
    if dry_run:
        return
    if _is_sqlite(db):
        db.execute(
            text(
                """
                INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                VALUES(:d, :t, :c)
                ON CONFLICT(department_id, diet_type_id)
                DO UPDATE SET default_count=excluded.default_count
                """
            ),
            {"d": dept_id, "t": str(diet_type_id), "c": int(count)},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                VALUES(:d, :t, :c)
                ON CONFLICT(department_id, diet_type_id)
                DO UPDATE SET default_count=excluded.default_count, updated_at=now()
                """
            ),
            {"d": dept_id, "t": str(diet_type_id), "c": int(count)},
        )


def _validate_payload(payload: dict) -> list[dict]:
    site_name = str(payload.get("site_name") or "").strip()
    if not site_name:
        raise ValueError("payload.site_name is required")
    if site_name != SITE_NAME_REQUIRED:
        raise ValueError(f"payload.site_name must be exactly '{SITE_NAME_REQUIRED}'")

    departments = payload.get("departments")
    if not isinstance(departments, list) or not departments:
        raise ValueError("payload.departments must be a non-empty list")

    out: list[dict] = []
    seen: set[str] = set()
    for dep in departments:
        if not isinstance(dep, dict):
            raise ValueError("each department must be an object")
        name = str(dep.get("name") or "").strip()
        if not name:
            raise ValueError("department.name is required")
        if name.lower() in seen:
            raise ValueError(f"duplicate department name in payload: {name}")
        seen.add(name.lower())

        rc = dep.get("resident_count")
        if rc is None:
            raise ValueError(f"department.resident_count is required for {name}")
        try:
            rc_i = int(rc)
        except Exception as exc:
            raise ValueError(f"department.resident_count must be int for {name}") from exc
        if rc_i < 0:
            raise ValueError(f"department.resident_count must be >= 0 for {name}")

        diets = dep.get("clear_special_diets", {})
        if diets is None:
            diets = {}
        if not isinstance(diets, dict):
            raise ValueError(f"department.clear_special_diets must be an object for {name}")

        norm_diets: dict[str, int] = {}
        for dname, cnt in diets.items():
            dn = _normalize_diet_name(str(dname or "").strip())
            if not dn:
                continue
            try:
                c = int(cnt)
            except Exception as exc:
                raise ValueError(f"diet count must be int for {name}/{dn}") from exc
            if c < 0:
                raise ValueError(f"diet count must be >= 0 for {name}/{dn}")
            norm_diets[dn] = c

        out.append({"name": name, "resident_count": rc_i, "clear_special_diets": norm_diets})
    return out


def run(input_path: str, dry_run: bool) -> int:
    payload = _load_json(input_path)
    departments = _validate_payload(payload)
    diet_family_by_name = _build_diet_family_map(payload, departments)

    app = create_app()
    summary = Summary()

    with app.app_context():
        db = get_session()
        try:
            _ensure_department_table_shape(db)
            _ensure_dietary_types_table_shape(db)
            _ensure_defaults_table_shape(db)

            site_id, site_tenant_id = _resolve_site_context(db, SITE_NAME_REQUIRED)
            known_diet_ids_by_name: dict[str, str] = {}

            # Prime cache with existing site-scoped diet types to improve reuse accounting.
            for row in db.execute(
                text("SELECT id, name FROM dietary_types WHERE site_id=:s"),
                {"s": site_id},
            ).fetchall():
                did = str(row[0])
                dname = _normalize_diet_name(str(row[1] or ""))
                if dname:
                    known_diet_ids_by_name[dname.lower()] = did

            for dep in departments:
                dep_name = dep["name"]
                resident_count = int(dep["resident_count"])
                diets = dep["clear_special_diets"]

                existing_dep = _get_dept_by_name(db, site_id=site_id, name=dep_name)
                if not existing_dep:
                    summary.departments_created += 1
                    _create_department(db, site_id=site_id, name=dep_name, resident_count=resident_count, dry_run=dry_run)
                    existing_dep = _get_dept_by_name(db, site_id=site_id, name=dep_name)
                    if not existing_dep and dry_run:
                        # Predictable dry-run placeholder to let summary logic continue.
                        dept_id = f"dry-run::{dep_name}"
                    elif not existing_dep:
                        raise RuntimeError(f"Department not found after create: {dep_name}")
                    else:
                        dept_id = str(existing_dep[0])
                else:
                    dept_id = str(existing_dep[0])
                    old_mode = str(existing_dep[1] or "fixed")
                    old_count = int(existing_dep[2] or 0)
                    needs_update = old_mode != "fixed" or old_count != resident_count
                    if needs_update:
                        summary.departments_updated += 1
                        _update_department_counts(db, dept_id=dept_id, resident_count=resident_count, dry_run=dry_run)
                    else:
                        summary.departments_unchanged += 1

                for diet_name, count in diets.items():
                    dt_id = _resolve_or_create_diet_type_id(
                        db,
                        site_id=site_id,
                        diet_name=diet_name,
                        dry_run=dry_run,
                        summary=summary,
                        diet_family_by_name=diet_family_by_name,
                        known_diet_ids_by_name=known_diet_ids_by_name,
                        site_tenant_id=site_tenant_id,
                    )
                    if not dt_id:
                        continue

                    existing_count = None
                    if not dt_id.startswith("dry-run::") and not dept_id.startswith("dry-run::"):
                        existing_count = _get_existing_binding_count(db, dept_id=dept_id, diet_type_id=dt_id)

                    if existing_count is None:
                        summary.bindings_created += 1
                    elif existing_count != int(count):
                        summary.bindings_updated += 1
                    else:
                        summary.bindings_unchanged += 1

                    _upsert_binding(db, dept_id=dept_id, diet_type_id=dt_id, count=int(count), dry_run=dry_run)

            if dry_run:
                db.rollback()
            else:
                db.commit()

            print("=== Östergården seed summary ===")
            print(f"site: {SITE_NAME_REQUIRED} (id={site_id})")
            print(f"dry_run: {str(dry_run).lower()}")
            print("departments:")
            print(f"  created: {summary.departments_created}")
            print(f"  updated: {summary.departments_updated}")
            print(f"  unchanged: {summary.departments_unchanged}")
            print("diet types:")
            print(f"  created: {summary.diets_created}")
            print(f"  reused: {summary.diets_reused}")
            print(f"  family_updated: {summary.diet_family_updates}")
            print(f"  ignored_non_diet_entries: {summary.ignored_diets}")
            print("diet bindings (department_diet_defaults):")
            print(f"  created: {summary.bindings_created}")
            print(f"  updated: {summary.bindings_updated}")
            print(f"  unchanged: {summary.bindings_unchanged}")
            return 0
        except Exception as exc:
            db.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            db.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Östergården from JSON without creating a site")
    parser.add_argument("--input", required=True, help="Path to JSON input file")
    parser.add_argument("--dry-run", action="store_true", help="Plan and validate only; no changes committed")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    raise SystemExit(run(input_path=args.input, dry_run=bool(args.dry_run)))
