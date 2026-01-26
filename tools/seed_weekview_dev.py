"""Seed minimal data for site-level weekview dev repro.

Creates:
- Site: accept-site-A
- Department: depA under accept-site-A
- Dish: Pannkakor
- Published menu for year=2026, week=8 with Monday lunch alt1=Pannkakor

Run with DEV_CREATE_ALL=1 so schema is available.
"""
from __future__ import annotations

from sqlalchemy import text
import sys, os
# Ensure project root on sys.path when running from tools/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from core.app_factory import create_app
from core.db import get_session


def main():
    app = create_app({"TESTING": False, "SECRET_KEY": "dev"})
    db = get_session()
    try:
        # Sites (ensure tenant_id=1 exists for dev)
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
        # Add tenant_id column if missing (dev only)
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('sites')")).fetchall()}
        if "tenant_id" not in cols:
            db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,name,tenant_id) VALUES('accept-site-A','Site A',1)"))
        db.execute(text("UPDATE sites SET tenant_id=1 WHERE id='accept-site-A'"))
        # Departments (handle legacy vs canonical columns)
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
        if {"resident_count_mode", "resident_count_fixed", "version", "site_id"}.issubset(cols):
            db.execute(text(
                "INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES('depA','accept-site-A','Avd A','fixed',10,0)"
            ))
        else:
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, name TEXT, site_id TEXT, resident_count_fixed INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,name,site_id,resident_count_fixed) VALUES('depA','Avd A','accept-site-A',10)"))
        # Dishes/Menus/Variants
        db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER, name TEXT, category TEXT)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER, year INTEGER, week INTEGER, status TEXT, updated_at TEXT)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
        # Dish
        db.execute(text("INSERT OR IGNORE INTO dishes(tenant_id,name,category) VALUES(1,'Pannkakor',NULL)"))
        did_row = db.execute(text("SELECT id FROM dishes WHERE name='Pannkakor' AND tenant_id=1")).fetchone()
        did = int(did_row[0]) if did_row else 1
        if not did_row:
            db.execute(text("INSERT INTO dishes(id,tenant_id,name,category) VALUES(1,1,'Pannkakor',NULL)"))
            did = 1
        # Menu
        db.execute(text("INSERT OR IGNORE INTO menus(tenant_id,year,week,status,updated_at) VALUES(1,2026,8,'published','2026-01-01T00:00:00Z')"))
        mid_row = db.execute(text("SELECT id FROM menus WHERE tenant_id=1 AND year=2026 AND week=8 AND status='published'"))
        mid_row = mid_row.fetchone()
        if not mid_row:
            db.execute(text("INSERT INTO menus(tenant_id,year,week,status,updated_at) VALUES(1,2026,8,'published','2026-01-01T00:00:00Z')"))
            mid_row = db.execute(text("SELECT id FROM menus WHERE tenant_id=1 AND year=2026 AND week=8 AND status='published'"))
            mid_row = mid_row.fetchone()
        mid = int(mid_row[0])
        # Variant: Monday lunch alt1
        db.execute(text("INSERT OR IGNORE INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(:mid,'mon','lunch','alt1',:did)"), {"mid": mid, "did": did})
        db.commit()
    finally:
        db.close()
    print("Seeded site accept-site-A, depA, published week 8/2026 with Monday lunch.")


if __name__ == "__main__":
    main()
