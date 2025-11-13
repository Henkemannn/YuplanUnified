"""Seed Varberg Midsommargården tenant/site, departments, diet types/defaults, notes and Alt2 flags.

Idempotent: re-runs will upsert and avoid duplicates. Prints created IDs and final collection ETags.

Usage:
  DATABASE_URL=... python -m scripts.seed_varberg_midsommar
"""
from __future__ import annotations

import os
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.db import init_engine, get_session
from core.admin_repo import SitesRepo, DepartmentsRepo, Alt2Repo, _is_sqlite
from core.etag import make_collection_etag

SITE_NAME = "Varberg Midsommargården"
SITE_SLUG = "varberg-midsommar"

DEPARTMENTS = [
    {"name": "Avd 1", "resident_count_mode": "fixed", "resident_count_fixed": 24},
    {"name": "Avd 2", "resident_count_mode": "fixed", "resident_count_fixed": 22},
]

DIET_TYPES = ["Glutenfri", "Laktosfri", "Vegetarisk", "Timbal"]

DIET_DEFAULTS = {
    "Avd 1": {"Glutenfri": 2, "Laktosfri": 1, "Timbal": 1},
    "Avd 2": {"Glutenfri": 1, "Vegetarisk": 1},
}

SITE_NOTE = "Undvik ris på fredagar. Mos som alternativ vid behov."
DEPT_NOTES = {
    "Avd 1": "Kaffe efter 14 serveras koffeinfritt.",
    "Avd 2": "Extra mos till rum 203.",
}

ALT2_WEEK = 51
ALT2_FLAGS = {
    "Avd 1": [2, 4],  # weekdays enabled
    "Avd 2": [3, 5],
}


def run() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL env required", file=sys.stderr)
        return 1

    init_engine(url)
    # Use repo instances; they manage sessions internally
    sites_repo = SitesRepo()
    depts_repo = DepartmentsRepo()
    alt2_repo = Alt2Repo()

    # 1) Create site (or fetch existing by name)
    existing_sites = sites_repo.list_sites()
    site = next((s for s in existing_sites if s.get("name") == SITE_NAME), None)
    if site:
        site_id = site["id"]
    else:
        created, _ = sites_repo.create_site(SITE_NAME)
        site_id = created["id"]
    print(f"Site: {SITE_NAME} -> id={site_id}")

    # 2) Departments upsert
    dept_ids: dict[str, str] = {}
    current = {x["name"]: x for x in depts_repo.list_for_site(site_id)}
    for d in DEPARTMENTS:
        name = d["name"]
        existing = current.get(name)
        if existing:
            dept_ids[name] = existing["id"]
            # update resident fields only if changed
            updates: dict[str, Any] = {}
            if existing.get("resident_count_mode") != d["resident_count_mode"]:
                updates["resident_count_mode"] = d["resident_count_mode"]
            if int(existing.get("resident_count_fixed", 0)) != int(d.get("resident_count_fixed", 0)):
                updates["resident_count_fixed"] = int(d.get("resident_count_fixed", 0))
            if updates:
                depts_repo.update_department(existing["id"], existing.get("version", 0), **updates)
        else:
            created, _ = depts_repo.create_department(
                site_id,
                name,
                d.get("resident_count_mode", "fixed"),
                int(d.get("resident_count_fixed", 0)),
            )
            dept_ids[name] = created["id"]
    print("Departments:", dept_ids)

    # 3) Diet types ensure (cross-dialect). For SQLite, create table; for Postgres, upsert rows.
    db = get_session()
    try:
        if _is_sqlite(db):
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS diet_types (
                        id TEXT PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL
                    )
                    """
                )
            )
            for n in DIET_TYPES:
                db.execute(
                    text("INSERT OR IGNORE INTO diet_types (id, name) VALUES (:id,:name)"),
                    {"id": n.lower(), "name": n},
                )
        else:
            # On Postgres, table exists from migrations with additional columns and defaults.
            for n in DIET_TYPES:
                db.execute(
                    text(
                        """
                        INSERT INTO diet_types (id, name)
                        VALUES (:id, :name)
                        ON CONFLICT (id) DO NOTHING
                        """
                    ),
                    {"id": n.lower(), "name": n},
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Helper: ensure all required diet_type ids exist (cross-dialect)
    def _ensure_diet_type_ids(ids: list[str]):
        s = get_session()
        try:
            existing = {r[0] for r in s.execute(text("SELECT id FROM diet_types"))}
            missing = [i for i in ids if i not in existing]
            if missing:
                for m in missing:
                    s.execute(
                        text(
                            """
                            INSERT INTO diet_types (id, name)
                            VALUES (:id, :name)
                            ON CONFLICT (id) DO NOTHING
                            """
                        ),
                        {"id": m, "name": m.capitalize()},
                    )
                s.commit()
        finally:
            s.close()

    # 4) Diet defaults upsert (via DepartmentsRepo optimistic bump)
    all_needed_diet_ids = {diet.lower() for mapping in DIET_DEFAULTS.values() for diet in mapping.keys()}
    _ensure_diet_type_ids(sorted(all_needed_diet_ids))
    # Debug: list diet_types after ensure
    dbg = get_session()
    try:
        rows = list(dbg.execute(text("SELECT id, name FROM diet_types ORDER BY id")))
        print("Diet types existing:", [(r[0], r[1]) for r in rows])
    finally:
        dbg.close()
    for dept_name, mapping in DIET_DEFAULTS.items():
        dept_id = dept_ids.get(dept_name)
        if not dept_id:
            continue
        items = [
            {"diet_type_id": diet.lower(), "default_count": int(cnt)}
            for diet, cnt in mapping.items()
        ]
        current_ver = depts_repo.get_version(dept_id) or 0
        try:
            depts_repo.upsert_department_diet_defaults(dept_id, current_ver, items)
        except IntegrityError:
            # Fallback: create missing diet types then retry once
            missing_ids = []
            for it in items:
                # Quick existence check
                s2 = get_session()
                try:
                    row = s2.execute(text("SELECT 1 FROM diet_types WHERE id=:i"), {"i": it["diet_type_id"]}).fetchone()
                    if not row:
                        missing_ids.append(it["diet_type_id"])
                finally:
                    s2.close()
            if missing_ids:
                _ensure_diet_type_ids(missing_ids)
                depts_repo.upsert_department_diet_defaults(dept_id, current_ver, items)
    print("Diet defaults set")

    # 5) Notes upsert (departments only, using department notes field if present)
    for dept_name, note in DEPT_NOTES.items():
        did = dept_ids.get(dept_name)
        if not did:
            continue
        ver = depts_repo.get_version(did) or 0
        try:
            depts_repo.update_department_notes(did, ver, note)
        except Exception:
            # If notes column not present, skip gracefully
            pass
    print("Notes upserted (where supported)")

    # 6) Alt2 flags for week
    week = ALT2_WEEK
    flags: list[dict] = []
    for dept_name, days in ALT2_FLAGS.items():
        did = dept_ids.get(dept_name)
        if not did:
            continue
        for d in days:
            flags.append(
                {
                    "site_id": site_id,
                    "department_id": did,
                    "week": week,
                    "weekday": int(d),
                    "enabled": True,
                }
            )
    if flags:
        alt2_repo.bulk_upsert(flags)
    # Print ETag for Alt2
    alt2_version = alt2_repo.collection_version(week)
    alt2_etag = make_collection_etag("admin:alt2", f"week:{week}", alt2_version or 0)
    print(f"Alt2 week={week} ETag={alt2_etag}")

    # 7) Print departments collection ETag
    # Use max version across departments in site
    deps = depts_repo.list_for_site(site_id)
    max_ver = max((int(x.get("version", 0)) for x in deps), default=0)
    dep_etag = make_collection_etag("admin:departments", f"site:{site_id}", max_ver)
    print(f"Departments(site={site_id}) ETag={dep_etag}")

    return 0


if __name__ == "__main__":
    rc = run()
    sys.exit(rc)
