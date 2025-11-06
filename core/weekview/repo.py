from __future__ import annotations

from typing import Optional, Tuple

from flask import current_app


class WeekviewRepo:
    """Repository stub for Weekview (Phase A: no real persistence yet).

    In Phase B this will use SQLAlchemy/SQL to query the underlying Postgres tables.
    For Phase A, get_version returns 0 to allow ETag scaffolding and contract tests.
    """

    def get_weekview(self, tenant_id: int | str, year: int, week: int, department_id: Optional[str]) -> dict:
        # Phase A: return an empty schema-valid payload
        return {
            "year": year,
            "week": week,
            "week_start": None,
            "week_end": None,
            "department_summaries": [],
        }

    def get_version(self, tenant_id: int | str, year: int, week: int, department_id: str) -> int:
        # Phase A: always return version 0; Phase B will read from weekview_versions
        return 0

    def toggle_marks(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise NotImplementedError("Phase B")
