from __future__ import annotations

import argparse

from core.planera_v2.dev_runner import format_dev_run_report, run_planera_v2_from_current_day


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Planera 2.0 dev flow from current day state.")
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--iso-date", required=True, help="ISO date, e.g. 2026-04-16")
    parser.add_argument("--meal-key", required=True, help="Meal key, e.g. lunch, dinner, kvallsmat, dessert")
    parser.add_argument("--tenant-id", default="1")
    args = parser.parse_args()

    run = run_planera_v2_from_current_day(
        tenant_id=args.tenant_id,
        site_id=args.site_id,
        iso_date=args.iso_date,
        meal_key=args.meal_key,
    )
    print(format_dev_run_report(run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
