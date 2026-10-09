from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from .department_menu_row_demand_repo import DepartmentMenuRowDemandRepo
from .models import Department
from .db import get_session
from .commun_builder_publication import CommunBuilderPublicationService


class DepartmentMenuRowDemandError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DepartmentMenuRowDemandWriteInput:
    tenant_id: int
    site_id: str
    department_id: str
    year: int
    week: int
    weekday: int
    builder_menu_id: str
    builder_menu_version: int
    builder_menu_row_id: str
    selection_group_id: str | None
    quantity: int


_WEEKDAY_BY_NAME = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}


def _fail(code: str) -> None:
    raise DepartmentMenuRowDemandError(code)


def _normalize_positive_int(value: Any, code: str) -> int:
    if isinstance(value, bool):
        _fail(code)
    try:
        normalized = int(value)
    except Exception as exc:
        raise DepartmentMenuRowDemandError(code) from exc
    if normalized <= 0:
        _fail(code)
    return normalized


def _normalize_nonnegative_int(value: Any, code: str) -> int:
    if isinstance(value, bool):
        _fail(code)
    try:
        normalized = int(value)
    except Exception as exc:
        raise DepartmentMenuRowDemandError(code) from exc
    if normalized < 0:
        _fail(code)
    return normalized


def _normalize_identity(value: Any, code: str) -> str:
    identity = str(value or "").strip()
    if not identity:
        _fail(code)
    return identity


def _normalize_optional_selection_group(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        _fail("selection_group_id_invalid")
    group_id = str(value).strip()
    if not group_id:
        _fail("selection_group_id_invalid")
    return group_id


def _normalize_weekday(value: Any) -> int:
    if isinstance(value, bool):
        _fail("weekday_invalid")
    if isinstance(value, int):
        weekday = value
    else:
        raw = str(value or "").strip().lower()
        if not raw:
            _fail("weekday_invalid")
        if raw in _WEEKDAY_BY_NAME:
            return _WEEKDAY_BY_NAME[raw]
        try:
            weekday = int(raw)
        except Exception as exc:
            raise DepartmentMenuRowDemandError("weekday_invalid") from exc
    if weekday < 1 or weekday > 7:
        _fail("weekday_invalid")
    return weekday


def _weekday_name(weekday: int) -> str:
    for name, number in _WEEKDAY_BY_NAME.items():
        if int(number) == int(weekday):
            return name
    _fail("weekday_invalid")
    return ""


def _load_revision_snapshot(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    builder_menu_version: int,
) -> tuple[dict[str, Any], Any]:
    publication_service = CommunBuilderPublicationService()
    revision = publication_service.get_publication_revision_for_version(
        tenant_id=tenant_id,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=builder_menu_id,
        builder_menu_version=builder_menu_version,
    )
    if revision is None:
        _fail("publication_revision_missing")
    snapshot_json = str(revision.projection_snapshot_json or "").strip()
    if not snapshot_json:
        _fail("publication_revision_snapshot_missing")
    try:
        snapshot = json.loads(snapshot_json)
    except Exception as exc:
        raise DepartmentMenuRowDemandError("publication_revision_snapshot_invalid") from exc
    if not isinstance(snapshot, dict):
        _fail("publication_revision_snapshot_invalid")
    if (
        int(snapshot.get("tenant_id") or 0) != int(tenant_id)
        or str(snapshot.get("site_id") or "") != str(site_id)
        or int(snapshot.get("year") or 0) != int(year)
        or int(snapshot.get("week") or 0) != int(week)
        or str(snapshot.get("builder_menu_id") or "") != str(builder_menu_id)
        or int(snapshot.get("builder_menu_version") or 0) != int(builder_menu_version)
    ):
        _fail("publication_revision_mismatch")
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        _fail("publication_revision_snapshot_invalid")
    return snapshot, revision


def _find_snapshot_row(snapshot: dict[str, Any], builder_menu_row_id: str) -> dict[str, Any] | None:
    for row in snapshot.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("builder_menu_row_id") or "").strip() == str(builder_menu_row_id):
            return row
    return None


class DepartmentMenuRowDemandService:
    def __init__(self, *, repository: DepartmentMenuRowDemandRepo | None = None) -> None:
        self._repository = repository or DepartmentMenuRowDemandRepo()

    def _load_department(self, *, tenant_id: int, site_id: str, department_id: str) -> Department:
        db = get_session()
        try:
            department = db.get(Department, str(department_id))
            if department is None:
                _fail("department_not_found")
            if str(department.site_id) != str(site_id):
                _fail("department_site_mismatch")
            site = db.execute(
                text("SELECT tenant_id FROM sites WHERE id = :site_id"),
                {"site_id": str(site_id)},
            ).fetchone()
            if site is None or site[0] is None or int(site[0]) != int(tenant_id):
                _fail("department_tenant_mismatch")
            return department
        finally:
            db.close()

    def write_for_row(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: Any,
        builder_menu_id: str,
        builder_menu_version: int,
        builder_menu_row_id: str,
        selection_group_id: Any,
        quantity: Any,
    ) -> dict[str, Any]:
        normalized_input = DepartmentMenuRowDemandWriteInput(
            tenant_id=_normalize_positive_int(tenant_id, "tenant_id_invalid"),
            site_id=_normalize_identity(site_id, "site_id_missing"),
            department_id=_normalize_identity(department_id, "department_id_missing"),
            year=_normalize_positive_int(year, "year_invalid"),
            week=_normalize_positive_int(week, "week_invalid"),
            weekday=_normalize_weekday(weekday),
            builder_menu_id=_normalize_identity(builder_menu_id, "builder_menu_id_missing"),
            builder_menu_version=_normalize_positive_int(builder_menu_version, "builder_menu_version_invalid"),
            builder_menu_row_id=_normalize_identity(builder_menu_row_id, "builder_menu_row_id_missing"),
            selection_group_id=_normalize_optional_selection_group(selection_group_id),
            quantity=_normalize_nonnegative_int(quantity, "quantity_invalid"),
        )

        self._load_department(
            tenant_id=normalized_input.tenant_id,
            site_id=normalized_input.site_id,
            department_id=normalized_input.department_id,
        )
        snapshot, revision = _load_revision_snapshot(
            tenant_id=normalized_input.tenant_id,
            site_id=normalized_input.site_id,
            year=normalized_input.year,
            week=normalized_input.week,
            builder_menu_id=normalized_input.builder_menu_id,
            builder_menu_version=normalized_input.builder_menu_version,
        )
        row = _find_snapshot_row(snapshot, normalized_input.builder_menu_row_id)
        if row is None:
            _fail("published_row_missing")
        published_weekday = _normalize_weekday(str(row.get("day") or ""))
        if published_weekday != normalized_input.weekday:
            _fail("weekday_mismatch")
        published_group = _normalize_optional_selection_group(row.get("selection_group_id"))
        if published_group != normalized_input.selection_group_id:
            _fail("selection_group_mismatch")
        return self._repository.upsert_for_row(
            tenant_id=normalized_input.tenant_id,
            site_id=normalized_input.site_id,
            department_id=normalized_input.department_id,
            year=normalized_input.year,
            week=normalized_input.week,
            weekday=normalized_input.weekday,
            builder_menu_id=normalized_input.builder_menu_id,
            builder_menu_version=normalized_input.builder_menu_version,
            builder_menu_row_id=normalized_input.builder_menu_row_id,
            selection_group_id=normalized_input.selection_group_id,
            quantity=normalized_input.quantity,
        )

    def get_for_row(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: Any,
        builder_menu_id: str,
        builder_menu_version: int,
        builder_menu_row_id: str,
    ) -> dict[str, Any] | None:
        return self._repository.get_for_row(
            tenant_id=_normalize_positive_int(tenant_id, "tenant_id_invalid"),
            site_id=_normalize_identity(site_id, "site_id_missing"),
            department_id=_normalize_identity(department_id, "department_id_missing"),
            year=_normalize_positive_int(year, "year_invalid"),
            week=_normalize_positive_int(week, "week_invalid"),
            weekday=_normalize_weekday(weekday),
            builder_menu_id=_normalize_identity(builder_menu_id, "builder_menu_id_missing"),
            builder_menu_version=_normalize_positive_int(builder_menu_version, "builder_menu_version_invalid"),
            builder_menu_row_id=_normalize_identity(builder_menu_row_id, "builder_menu_row_id_missing"),
        )

    def list_for_department_weekday(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: Any,
    ) -> list[dict[str, Any]]:
        return self._repository.list_for_department_weekday(
            tenant_id=_normalize_positive_int(tenant_id, "tenant_id_invalid"),
            site_id=_normalize_identity(site_id, "site_id_missing"),
            department_id=_normalize_identity(department_id, "department_id_missing"),
            year=_normalize_positive_int(year, "year_invalid"),
            week=_normalize_positive_int(week, "week_invalid"),
            weekday=_normalize_weekday(weekday),
        )

    def list_for_selection_group(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: Any,
        selection_group_id: Any,
    ) -> list[dict[str, Any]]:
        return self._repository.list_for_selection_group(
            tenant_id=_normalize_positive_int(tenant_id, "tenant_id_invalid"),
            site_id=_normalize_identity(site_id, "site_id_missing"),
            department_id=_normalize_identity(department_id, "department_id_missing"),
            year=_normalize_positive_int(year, "year_invalid"),
            week=_normalize_positive_int(week, "week_invalid"),
            weekday=_normalize_weekday(weekday),
            selection_group_id=_normalize_optional_selection_group(selection_group_id),
        )

    def list_for_builder_menu_row_id(
        self,
        *,
        tenant_id: int,
        site_id: str,
        builder_menu_row_id: str,
    ) -> list[dict[str, Any]]:
        return self._repository.list_for_builder_menu_row_id(
            tenant_id=_normalize_positive_int(tenant_id, "tenant_id_invalid"),
            site_id=_normalize_identity(site_id, "site_id_missing"),
            builder_menu_row_id=_normalize_identity(builder_menu_row_id, "builder_menu_row_id_missing"),
        )
