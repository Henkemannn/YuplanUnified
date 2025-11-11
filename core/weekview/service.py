from __future__ import annotations

import re
from typing import Optional, Sequence

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
        version = 0 if not department_id else self.repo.get_version(tenant_id, year, week, department_id)
        payload = self.repo.get_weekview(tenant_id, year, week, department_id)
        etag = self.build_etag(tenant_id, dep, year, week, version)
        return payload, etag


class EtagMismatchError(Exception):
    pass


class WeekviewService(WeekviewService):  # type: ignore[misc]
    _ETAG_RE = re.compile(r'^W/"weekview:dept:(?P<dep>[0-9a-fA-F\-]+):year:(?P<yy>\d{4}):week:(?P<ww>\d{1,2}):v(?P<v>\d+)"$')

    def toggle_marks(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        ops: Sequence[dict],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        # Validate target tuple in ETag matches request
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_version = self.repo.apply_operations(tenant_id, year, week, department_id, ops)
        return self.build_etag(tenant_id, department_id, year, week, new_version)

    def fetch_weekview_conditional(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str | None,
        if_none_match: str | None,
    ) -> tuple[bool, dict | None, str]:
        """
        Returns (not_modified, payload, etag). If not_modified is True, payload will be None.
        """
        dep = department_id or "__none__"
        version = 0 if not department_id else self.repo.get_version(tenant_id, year, week, department_id)
        etag = self.build_etag(tenant_id, dep, year, week, version)
        if if_none_match and if_none_match == etag:
            return True, None, etag
        payload = self.repo.get_weekview(tenant_id, year, week, department_id)
        return False, payload, etag

    def update_residents_counts(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        items: Sequence[dict],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_v = self.repo.set_residents_counts(tenant_id, year, week, department_id, items)
        return self.build_etag(tenant_id, department_id, year, week, new_v)

    def update_alt2_flags(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        days: Sequence[int],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_v = self.repo.set_alt2_flags(tenant_id, year, week, department_id, days)
        return self.build_etag(tenant_id, department_id, year, week, new_v)
