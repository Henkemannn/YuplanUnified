from __future__ import annotations

"""One-off seed importer for service addons per site from structured JSON.

Safe behavior:
- Never creates sites.
- No deletes.
- No schema changes.
- Idempotent: create missing addons, reuse existing.
- Operates only for the provided site context.

Usage:
  python scripts/seed_service_addons.py --input scripts/service_addons.json --dry-run
  python scripts/seed_service_addons.py --input scripts/service_addons.json
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


@dataclass
class Summary:
    created: int = 0
    reused: int = 0
    unchanged: int = 0


def _load_json(path: str) -> dict:
    import json

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object")
    return payload


def _table_has_column(db, table_name: str, column_name: str) -> bool:
    try:
        # SQLite path
        cols = db.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        if cols:
            return any(str(c[1]) == column_name for c in cols)
    except Exception:
        pass

    try:
        # Postgres path
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
    except Exception:
        return False


def _resolve_site_id(db, site_name: str) -> str:
    row = db.execute(
        text("SELECT id FROM sites WHERE lower(trim(name)) = lower(trim(:n)) ORDER BY id LIMIT 1"),
        {"n": site_name},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Site '{site_name}' not found. This script never creates sites.")
    return str(row[0])


def _normalize_addon_name(name: str) -> str:
    return " ".join(str(name or "").strip().split())


def _validate_payload(payload: dict) -> tuple[str, list[str]]:
    site_name = str(payload.get("site_name") or "").strip()
    if not site_name:
        raise ValueError("payload.site_name is required")

    items = payload.get("service_addons")
    if not isinstance(items, list) or not items:
        raise ValueError("payload.service_addons must be a non-empty list")

    out: list[str] = []
    for raw in items:
        nm = _normalize_addon_name(str(raw or ""))
        if not nm:
            continue
        out.append(nm)

    if not out:
        raise ValueError("payload.service_addons contains no valid names")

    return site_name, out


def _find_existing_addon(db, *, name: str, site_id: str, has_site_id_col: bool):
    if has_site_id_col:
        return db.execute(
            text(
                """
                SELECT id
                FROM service_addons
                WHERE site_id=:sid AND lower(trim(name)) = lower(trim(:n))
                LIMIT 1
                """
            ),
            {"sid": site_id, "n": name},
        ).fetchone()

    # Legacy schema (global unique name)
    return db.execute(
        text(
            """
            SELECT id
            FROM service_addons
            WHERE lower(trim(name)) = lower(trim(:n))
            LIMIT 1
            """
        ),
        {"n": name},
    ).fetchone()


def _create_addon(db, *, name: str, site_id: str, has_site_id_col: bool, dry_run: bool) -> None:
    if dry_run:
        return

    import uuid

    new_id = str(uuid.uuid4())
    if has_site_id_col:
        db.execute(
            text(
                """
                INSERT INTO service_addons(id, site_id, name, is_active, created_at)
                VALUES(:id, :sid, :n, 1, CURRENT_TIMESTAMP)
                """
            ),
            {"id": new_id, "sid": site_id, "n": name},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO service_addons(id, name, is_active, created_at)
                VALUES(:id, :n, 1, CURRENT_TIMESTAMP)
                """
            ),
            {"id": new_id, "n": name},
        )


def run(input_path: str, dry_run: bool) -> int:
    payload = _load_json(input_path)
    site_name, service_addons = _validate_payload(payload)

    app = create_app()
    summary = Summary()

    with app.app_context():
        db = get_session()
        try:
            # Safety checks: script must not mutate schema.
            tbl = db.execute(
                text(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type='table' AND name='service_addons'
                    """
                )
            ).fetchone()
            if tbl is None:
                # For non-sqlite, fallback to information_schema check.
                try:
                    chk = db.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_name='service_addons'
                            LIMIT 1
                            """
                        )
                    ).fetchone()
                    if chk is None:
                        raise RuntimeError("service_addons table not found")
                except Exception:
                    raise RuntimeError("service_addons table not found")

            site_id = _resolve_site_id(db, site_name)
            has_site_id_col = _table_has_column(db, "service_addons", "site_id")

            seen_in_payload: set[str] = set()
            for raw_name in service_addons:
                name = _normalize_addon_name(raw_name)
                key = name.lower()
                if key in seen_in_payload:
                    summary.unchanged += 1
                    continue
                seen_in_payload.add(key)

                existing = _find_existing_addon(
                    db,
                    name=name,
                    site_id=site_id,
                    has_site_id_col=has_site_id_col,
                )
                if existing is not None:
                    summary.reused += 1
                    continue

                _create_addon(
                    db,
                    name=name,
                    site_id=site_id,
                    has_site_id_col=has_site_id_col,
                    dry_run=dry_run,
                )
                summary.created += 1

            if dry_run:
                db.rollback()
            else:
                db.commit()

            print("=== Service addon seed summary ===")
            print(f"site: {site_name}")
            print(f"dry_run: {str(dry_run).lower()}")
            print("")
            print("addons:")
            print(f"  created: {summary.created}")
            print(f"  reused: {summary.reused}")
            print(f"  unchanged: {summary.unchanged}")
            return 0
        except Exception as exc:
            db.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            db.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed service addons for an existing site from JSON")
    parser.add_argument("--input", required=True, help="Path to JSON input file")
    parser.add_argument("--dry-run", action="store_true", help="Plan and validate only; no changes committed")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    raise SystemExit(run(input_path=args.input, dry_run=bool(args.dry_run)))
