from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .repo import ReportRepo


class ReportService:
    def __init__(self, repo: ReportRepo | None = None) -> None:
        self.repo = repo or ReportRepo()

    def _build_etag_dept(self, department_id: str, year: int, week: int, version: int) -> str:
        return f'W/"report:dept:{department_id}:year:{year}:week:{week}:v{version}"'

    def _build_etag_site(self, year: int, week: int, vmax: int, n: int) -> str:
        return f'W/"report:site:year:{year}:week:{week}:v{vmax}:n{n}"'

    def compute(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str | None,
        if_none_match: str | None = None,
    ) -> tuple[bool, dict, str]:
        """Return (not_modified, payload, etag)."""
        versions_map, vmax, n = self.repo.get_versions(tenant_id, year, week, department_id)
        # Build ETag
        if department_id:
            v = versions_map.get(department_id, 0)
            etag = self._build_etag_dept(department_id, year, week, v)
        else:
            etag = self._build_etag_site(year, week, vmax, n)
        if if_none_match and if_none_match == etag:
            return True, {}, etag
        # When department_id is specified but no data, treat as 404 at API layer; here we still aggregate empty
        residents = self.repo.get_residents(tenant_id, year, week, department_id)
        marks = self.repo.get_marks(tenant_id, year, week, department_id)
        # Aggregate per dept -> meal
        depts: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: {"lunch": defaultdict(int), "dinner": defaultdict(int)}
        )
        residents_totals: dict[tuple[str, str], int] = defaultdict(int)  # (dept, meal) -> total
        for r in residents:
            key = (r["department_id"], r["meal"])
            residents_totals[key] += int(r["count"]) if r["count"] is not None else 0
        for m in marks:
            diet = m["diet_type"]
            if str(diet).lower() == "normal":
                # "specials" should exclude normal diet entries
                continue
            dep = m["department_id"]
            meal = m["meal"]
            depts[dep][meal][diet] += 1
        # Build departments section
        department_ids: Iterable[str] = (
            versions_map.keys() if department_id is None else ([department_id] if department_id else [])
        )
        if not department_ids and not department_id:
            # If querying all but there are no versions, still produce empty list and zero totals
            department_ids = []
        meta = self.repo.get_dept_meta(tenant_id, department_ids)
        departments = []
        totals_meals = {
            "lunch": {"normal": 0, "specials": defaultdict(int), "total": 0},
            "dinner": {"normal": 0, "specials": defaultdict(int), "total": 0},
        }
        for dep in department_ids:
            lunch_specials = dict(depts[dep]["lunch"]) if dep in depts else {}
            dinner_specials = dict(depts[dep]["dinner"]) if dep in depts else {}
            lunch_sum_specials = sum(lunch_specials.values())
            dinner_sum_specials = sum(dinner_specials.values())
            lunch_res_total = residents_totals.get((dep, "lunch"), 0)
            dinner_res_total = residents_totals.get((dep, "dinner"), 0)
            lunch_normal = max(lunch_res_total - lunch_sum_specials, 0)
            dinner_normal = max(dinner_res_total - dinner_sum_specials, 0)
            dep_meta = meta.get(dep, {"department_name": None, "notes": None})
            departments.append(
                {
                    "department_id": dep,
                    "department_name": dep_meta.get("department_name"),
                    "notes": dep_meta.get("notes"),
                    "lunch": {
                        "normal": lunch_normal,
                        "specials": lunch_specials,
                        "total": lunch_normal + lunch_sum_specials,
                    },
                    "dinner": {
                        "normal": dinner_normal,
                        "specials": dinner_specials,
                        "total": dinner_normal + dinner_sum_specials,
                    },
                }
            )
            # Update totals
            totals_meals["lunch"]["normal"] += lunch_normal
            totals_meals["lunch"]["total"] += lunch_normal + lunch_sum_specials
            for k, v in lunch_specials.items():
                totals_meals["lunch"]["specials"][k] += v
            totals_meals["dinner"]["normal"] += dinner_normal
            totals_meals["dinner"]["total"] += dinner_normal + dinner_sum_specials
            for k, v in dinner_specials.items():
                totals_meals["dinner"]["specials"][k] += v
        totals = {
            "lunch": {
                "normal": totals_meals["lunch"]["normal"],
                "specials": dict(totals_meals["lunch"]["specials"]),
                "total": totals_meals["lunch"]["total"],
            },
            "dinner": {
                "normal": totals_meals["dinner"]["normal"],
                "specials": dict(totals_meals["dinner"]["specials"]),
                "total": totals_meals["dinner"]["total"],
            },
        }
        payload = {"year": year, "week": week, "departments": departments, "totals": totals}
        return False, payload, etag
