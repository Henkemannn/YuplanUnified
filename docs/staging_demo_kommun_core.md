# Staging – Demo Kommun core seed

This seed script prepares a clean demo environment for municipal (Kommun) flows: admin → portal → weekview → weekly report. It resets any previous demo data for the specific tenant and recreates a deterministic demo state.

## Script
- File: `scripts/seed_demo_kommun_core.py`
- How to run locally (Python 3.11):

```
python -m scripts.seed_demo_kommun_core
```

## Staging (Fly.io)
- App: `yuplan-unified-staging`
- Command:

```
fly ssh console -a yuplan-unified-staging -C "bash -lc 'python -m scripts.seed_demo_kommun_core'"
```

Notes:
- Idempotent for the “Demo Kommun” tenant; safely resets its site, departments, and menu for the demo week.

## Demo data
- Tenant: `Demo Kommun` (id=1 in the seed)
- Site: `Midsommargården`
- Departments:
  - `Avd 1` (16 boende), fixed resident count
  - `Avd 2` (14 boende), fixed resident count
- Diets: `Gluten`, `Laktos`, `Vegetarisk` with per-department default counts
- Menu: `year=2025`, `week=47`
  - Lunch & dinner dishes for all 7 days
  - Lunch `alt2` enabled on Tue/Thu
- Optional: Week 47 is chosen to align with the weekview/weekly tests.
