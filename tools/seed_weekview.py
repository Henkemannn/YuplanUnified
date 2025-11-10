from __future__ import annotations

import argparse
import os
import sys
import uuid
from typing import Sequence

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from core.db import init_engine  # noqa: E402
from core.weekview.repo import WeekviewRepo  # noqa: E402


def seed_week(repo: WeekviewRepo, tenant: str, year: int, week: int, departments: Sequence[str]) -> None:
    # Seed residents counts for lunch across 5 weekdays, and mark some specials
    for dep in departments:
        items = []
        for dow in range(1, 6):  # Mon-Fri
            items.append({"day_of_week": dow, "meal": "lunch", "count": 20 + dow})
        repo.set_residents_counts(tenant, year, week, dep, items)
        # Mark lactose_free on Mon/Wed, gluten_free on Tue
        ops = [
            {"day_of_week": 1, "meal": "lunch", "diet_type": "lactose_free", "marked": True},
            {"day_of_week": 3, "meal": "lunch", "diet_type": "lactose_free", "marked": True},
            {"day_of_week": 2, "meal": "lunch", "diet_type": "gluten_free", "marked": True},
        ]
        repo.apply_operations(tenant, year, week, dep, ops)
        # Alt2 days Tue/Thu
        repo.set_alt2_flags(tenant, year, week, dep, [2, 4])


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed weekview demo data (dev-only)")
    parser.add_argument("--tenant", default="1", help="Tenant id or key (string)")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--departments",
        nargs="*",
        help="Optional fixed department UUIDs; if omitted, two random UUIDs are generated",
    )
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "sqlite:///unified.db")
    init_engine(url, force=True)
    repo = WeekviewRepo()
    deps = args.departments or [str(uuid.uuid4()), str(uuid.uuid4())]
    seed_week(repo, args.tenant, args.year, args.week, deps)
    print("Seeded weekview for:")
    for d in deps:
        print(f" - department_id={d}")


if __name__ == "__main__":
    main()
