from __future__ import annotations

from typing import Optional, Tuple

from .models import WeekView
from .repo import WeekviewRepo


class WeekviewService:
    def __init__(self, repo: Optional[WeekviewRepo] = None) -> None:
        self.repo = repo or WeekviewRepo()

    def resolve(self, site: str, department_id: str, date: str) -> dict:
        # Phase A: minimal placeholder context
        return {"site": site, "department_id": department_id, "date": date}

    def build_etag(self, tenant_id: int | str, department_id: str, year: int, week: int, version: int) -> str:
        # Weak ETag format per spec
        return f'W/"weekview:dept:{department_id}:year:{year}:week:{week}:v{version}"'

    def fetch_weekview(self, tenant_id: int | str, year: int, week: int, department_id: Optional[str]) -> tuple[dict, str]:
        dep = department_id or "__none__"
        # For Phase A, version is always 0
        version = 0 if not department_id else self.repo.get_version(tenant_id, year, week, department_id)
        payload = self.repo.get_weekview(tenant_id, year, week, department_id)
        etag = self.build_etag(tenant_id, dep, year, week, version)
        return payload, etag
