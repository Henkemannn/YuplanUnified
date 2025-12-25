import os
import uuid
from datetime import date, timedelta

from sqlalchemy import text

# Ensure app context and DB helpers are accessible
from core.db import get_session, create_all


def iso_week_dates(year: int, week: int):
    jan4 = date(year, 1, 4)
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    week_monday = week1_monday + timedelta(weeks=week - 1)
    return [week_monday + timedelta(days=i) for i in range(7)]


def main():
    # Bootstrap DB if needed
    os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
    create_all()

    sess = get_session()
    try:
        site_id = str(uuid.uuid4())
        dept1_id = str(uuid.uuid4())
        dept2_id = str(uuid.uuid4())
        year, week = 2025, 10

        # Create site
        sess.execute(text("""
            INSERT OR IGNORE INTO sites (id, name, version)
            VALUES (:site_id, 'DemoSite', 0)
        """), {"site_id": site_id})

        # Create departments
        sess.execute(text("""
            INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version)
            VALUES (:d1, :s, 'Avd Alpha', 'fixed', 25, 0)
        """), {"d1": dept1_id, "s": site_id})
        sess.execute(text("""
            INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version)
            VALUES (:d2, :s, 'Avd Beta', 'fixed', 30, 0)
        """), {"d2": dept2_id, "s": site_id})

        # Seed weekview_items (menus)
        dates = iso_week_dates(year, week)
        for i, day_date in enumerate(dates, start=1):
            ds = day_date.isoformat()
            # Dept1: Lunch Mon-Fri (5), Dinner Mon-Thu (4)
            if i <= 5:
                sess.execute(text("""
                    INSERT INTO weekview_items (id, tenant_id, department_id, local_date, meal, title, notes, status, version)
                    VALUES (:id, 1, :dept, :dt, 'lunch', :title, NULL, 'planned', 0)
                """), {"id": str(uuid.uuid4()), "dept": dept1_id, "dt": ds, "title": f"Lunch Day {i}"})
            if i <= 4:
                sess.execute(text("""
                    INSERT INTO weekview_items (id, tenant_id, department_id, local_date, meal, title, notes, status, version)
                    VALUES (:id, 1, :dept, :dt, 'dinner', :title, NULL, 'planned', 0)
                """), {"id": str(uuid.uuid4()), "dept": dept1_id, "dt": ds, "title": f"Dinner Day {i}"})
            # Dept2: Full week lunches + dinners
            for meal in ("lunch", "dinner"):
                sess.execute(text("""
                    INSERT INTO weekview_items (id, tenant_id, department_id, local_date, meal, title, notes, status, version)
                    VALUES (:id, 1, :dept, :dt, :meal, :title, NULL, 'planned', 0)
                """), {"id": str(uuid.uuid4()), "dept": dept2_id, "dt": ds, "meal": meal, "title": f"{meal.title()} Day {i}"})

        # Seed residents overrides for weekview (optional; align with fixed counts)
        # Not strictly needed for diets view; fixed counts suffice.

        # Seed diet types and marks for specials (make a couple marked specials)
        # Ensure diet_types exist
        sess.execute(text("""
            INSERT OR IGNORE INTO diet_types (id, tenant_id, name, billing_type, version)
            VALUES ('normal', 1, 'Normalkost', 'none', 0)
        """))
        sess.execute(text("""
            INSERT OR IGNORE INTO diet_types (id, tenant_id, name, billing_type, version)
            VALUES ('gluten', 1, 'Gluten', 'debiterbar', 0)
        """))
        sess.execute(text("""
            INSERT OR IGNORE INTO diet_types (id, tenant_id, name, billing_type, version)
            VALUES ('laktos', 1, 'Laktos', 'debiterbar', 0)
        """))

        # Mark specials for a few days on dept1 and dept2
        for i, day_date in enumerate(dates, start=1):
            ds = day_date.isoformat()
            # Dept1: Gluten lunch special 2 on Mon/Tue
            if i in (1, 2):
                sess.execute(text("""
                    INSERT INTO weekview_registrations (id, tenant_id, department_id, local_date, meal, type, value, marked, diet_type_id, diet_name, version)
                    VALUES (:id, 1, :dept, :dt, 'lunch', 'diet', :value, 1, 'gluten', 'Gluten', 0)
                """), {"id": str(uuid.uuid4()), "dept": dept1_id, "dt": ds, "value": 2})
            # Dept2: Laktos dinner special 1 on Wed/Thu/Fri
            if i in (3, 4, 5):
                sess.execute(text("""
                    INSERT INTO weekview_registrations (id, tenant_id, department_id, local_date, meal, type, value, marked, diet_type_id, diet_name, version)
                    VALUES (:id, 1, :dept, :dt, 'dinner', 'diet', :value, 1, 'laktos', 'Laktos', 0)
                """), {"id": str(uuid.uuid4()), "dept": dept2_id, "dt": ds, "value": 1})

        # Optionally seed department diet defaults (for dept1)
        sess.execute(text("""
            INSERT OR IGNORE INTO department_diet_defaults (tenant_id, department_id, diet_type_id, count, version)
            VALUES (1, :dept, 'gluten', 1, 0)
        """), {"dept": dept1_id})
        sess.execute(text("""
            INSERT OR IGNORE INTO department_diet_defaults (tenant_id, department_id, diet_type_id, count, version)
            VALUES (1, :dept, 'laktos', 1, 0)
        """), {"dept": dept1_id})

        sess.commit()
        print("Seed complete. Site:", site_id)
        print("Departments:", dept1_id, dept2_id)
        print("Week:", year, week)
        print("Hint: Set session site_id to this site or ensure your admin session uses the created site.")
    finally:
        sess.close()


if __name__ == "__main__":
    main()
