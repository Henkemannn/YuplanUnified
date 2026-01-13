"""Seed script for local Department Portal demo.
Run: python scripts/seed_department_portal_demo.py
Prereq: DEV_CREATE_ALL optional (tables auto via migrations in real env)
"""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from core import create_app  # type: ignore
from core.db import get_session
from sqlalchemy import text

DEPT_ID = "11111111-2222-3333-4444-555555555555"
SITE_ID = "demo-site"
TENANT_ID = 1
YEAR = 2025
WEEK = 47

# Monday = weekday 1; Tuesday 2

SQL = [
    # Departments + notes
    ("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')", {}),
    ("CREATE TABLE IF NOT EXISTS department_notes(department_id TEXT PRIMARY KEY, notes TEXT)", {}),
    ("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,'Avd Demo','manual')", {"i": DEPT_ID, "s": SITE_ID}),
    ("INSERT OR REPLACE INTO department_notes(department_id, notes) VALUES(:i,'Inga nötter')", {"i": DEPT_ID}),
    # Weekview tables
    ("CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))", {}),
    ("CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))", {}),
    ("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))", {}),
    # Monday residents + diets + alt2
    ("INSERT OR REPLACE INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'lunch',12)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    ("INSERT OR REPLACE INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'dinner',9)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    ("INSERT OR REPLACE INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Gluten',1)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    ("INSERT OR REPLACE INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Laktos',1)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    ("INSERT OR REPLACE INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    # Tuesday lunch residents
    ("INSERT OR REPLACE INTO weekview_residents_count VALUES(:t,:d,:y,:w,2,'lunch',10)", {"t": TENANT_ID, "d": DEPT_ID, "y": YEAR, "w": WEEK}),
    # Alt2 choice storage table (menu choice) maps Monday Alt2
    ("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))", {}),
    ("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)", {"s": SITE_ID, "d": DEPT_ID, "w": WEEK}),
    # Menu tables minimal for Monday
    ("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)", {}),
    ("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)", {}),
    ("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)", {}),
    ("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)", {}),
    ("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)", {}),
    ("DELETE FROM menu_variants WHERE menu_id=501", {}),
    ("DELETE FROM menus WHERE id=501", {}),
    ("DELETE FROM dishes WHERE id IN (401,402,403,404)", {}),
    ("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(401,1,'Pannbiff med lök',NULL)", {}),
    ("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(402,1,'Fiskgratäng',NULL)", {}),
    ("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(403,1,'Fruktsallad',NULL)", {}),
    ("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(404,1,'Kvällsgröt',NULL)", {}),
    ("INSERT OR REPLACE INTO menus(id,tenant_id,week,year) VALUES(501,1,:w,:y)", {"w": WEEK, "y": YEAR}),
    ("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(501,'mon','lunch','alt1',401)", {}),
    ("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(501,'mon','lunch','alt2',402)", {}),
    ("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(501,'mon','dessert','dessert',403)", {}),
    ("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(501,'mon','dinner','dinner',404)", {}),
]

def main():
    create_app()  # initializes engine
    db = get_session()
    try:
        for sql, params in SQL:
            db.execute(text(sql), params)
        db.commit()
        print("Seed OK - department portal demo ready.")
        print(f"Department ID: {DEPT_ID}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
