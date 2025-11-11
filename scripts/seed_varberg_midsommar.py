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

from core.db import init_engine, get_session
from core.admin_repo import SitesRepo, DepartmentsRepo, DietDefaultsRepo, Alt2Repo
from core.notes_repo import NotesRepo  # if missing in project, adjust to actual notes repo import
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
    db = get_session()
    try:
        # 1) Create site (or fetch)
        site_id = None
        # Prefer a deterministic id by slug when using sqlite for tests; otherwise rely on repo
        try:
            site_id = SitesRepo.get_or_create(db, SITE_SLUG, SITE_NAME)  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback: try create_site/list_sites pattern
            try:
                existing = [s for s in SitesRepo.list_sites(db) if s.get("name") == SITE_NAME]
                if existing:
                    site_id = existing[0]["id"]
                else:
                    site = SitesRepo.create_site(db, SITE_NAME)
                    site_id = site["id"] if isinstance(site, dict) else site
            except Exception as ex:  # pragma: no cover
                print(f"Failed to upsert site: {ex}", file=sys.stderr)
                return 1
        if not site_id:
            print("Failed to ensure site", file=sys.stderr)
            return 1
        print(f"Site: {SITE_NAME} -> id={site_id}")

        # 2) Departments upsert
        dept_ids: dict[str, str] = {}
        for d in DEPARTMENTS:
            name = d["name"]
            existing = DepartmentsRepo.list_for_site(db, site_id)
            found = next((x for x in existing if x.get("name") == name), None)
            if found:
                dept_ids[name] = found["id"]
                # update resident mode/fixed if changed
                changed = False
                if found.get("resident_count_mode") != d["resident_count_mode"]:
                    found["resident_count_mode"] = d["resident_count_mode"]
                    changed = True
                if found.get("resident_count_fixed") != d["resident_count_fixed"]:
                    found["resident_count_fixed"] = d["resident_count_fixed"]
                    changed = True
                if changed:
                    DepartmentsRepo.update_department(db, found["id"], found)  # type: ignore[arg-type]
            else:
                created = DepartmentsRepo.create_department(
                    db,
                    site_id,
                    name,
                    d.get("resident_count_mode", "fixed"),
                    int(d.get("resident_count_fixed", 0)),
                )
                dept_ids[name] = created["id"] if isinstance(created, dict) else created
        print("Departments:", dept_ids)

        # 3) Diet types ensure (if diet types are a separate table; otherwise skip)
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS diet_types (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            """))
            for n in DIET_TYPES:
                db.execute(text("INSERT OR IGNORE INTO diet_types (id, name) VALUES (:id,:name)"),
                           {"id": n.lower(), "name": n})
            db.commit()
        except Exception:
            # If project models diet types differently, we just continue.
            db.rollback()

        # 4) Diet defaults upsert
        for dept_name, mapping in DIET_DEFAULTS.items():
            dept_id = dept_ids.get(dept_name)
            if not dept_id:
                continue
            # Fetch current defaults, then apply changes
            current = {x.get("diet_type_id"): int(x.get("default_count", 0)) for x in (DietDefaultsRepo.list_for_department(db, dept_id) or [])}
            # Merge
            to_set = {**current}
            for diet, cnt in mapping.items():
                key = diet.lower()
                to_set[key] = int(cnt)
            # Persist via repo (assume repo has upsert-like method; otherwise, naive replace)
            DietDefaultsRepo.replace_for_department(db, dept_id, to_set)  # type: ignore[attr-defined]
        print("Diet defaults set")

        # 5) Notes upsert (site + departments)
        try:
            NotesRepo.set_site_note(db, site_id, SITE_NOTE)  # type: ignore[attr-defined]
            for dept_name, note in DEPT_NOTES.items():
                did = dept_ids.get(dept_name)
                if did:
                    NotesRepo.set_department_note(db, did, note)  # type: ignore[attr-defined]
            print("Notes upserted")
        except Exception as ex:
            print(f"Notes upsert skipped/failed: {ex}")

        # 6) Alt2 flags for week
        week = ALT2_WEEK
        for dept_name, days in ALT2_FLAGS.items():
            did = dept_ids.get(dept_name)
            if not did:
                continue
            items = [{"department_id": did, "weekday": int(d), "enabled": True} for d in days]
            Alt2Repo.bulk_upsert(db, week, items)  # type: ignore[arg-type]
        # Print ETag for Alt2
        alt2_version = Alt2Repo.collection_version(db, week)
        alt2_etag = make_collection_etag("admin:alt2", f"week:{week}", alt2_version or 0)
        print(f"Alt2 week={week} ETag={alt2_etag}")

        # 7) Print departments collection ETag
        # Use max version across departments in site
        deps = DepartmentsRepo.list_for_site(db, site_id)
        max_ver = max((int(x.get("version", 0)) for x in deps), default=0)
        dep_etag = make_collection_etag("admin:departments", f"site:{site_id}", max_ver)
        print(f"Departments(site={site_id}) ETag={dep_etag}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    rc = run()
    sys.exit(rc)
