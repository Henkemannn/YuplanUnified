from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date as _date
from typing import Any

from sqlalchemy import text

from core.admin_repo import DepartmentServiceAddonsRepo
from core.commun_builder_publication import CommunBuilderPublicationService
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.residents_service import get_effective_residents_for_week
from portal.department.auth import DepartmentPortalScope
from portal.department.submission_service import DepartmentPortalWeekSubmissionService


_SV_MONTHS = {
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "maj",
    6: "jun",
    7: "jul",
    8: "aug",
    9: "sep",
    10: "okt",
    11: "nov",
    12: "dec",
}


def _week_span_label(year: int, week: int) -> str:
    start_date = _date.fromisocalendar(year, week, 1)
    end_date = _date.fromisocalendar(year, week, 7)
    if start_date.month == end_date.month and start_date.year == end_date.year:
        return f"{start_date.day}–{end_date.day} {_SV_MONTHS[start_date.month]}"
    return f"{start_date.day} {_SV_MONTHS[start_date.month]}–{end_date.day} {_SV_MONTHS[end_date.month]}"


def _week_date_bounds(year: int, week: int) -> tuple[_date, _date]:
    return _date.fromisocalendar(year, week, 1), _date.fromisocalendar(year, week, 7)


def _format_choice_status(status: dict[str, Any]) -> tuple[str, str, str | None]:
    raw_status = str(status.get("status") or "not_started")
    needs_review = bool(status.get("needs_review"))
    if raw_status == "complete" and not needs_review:
        return "Färdig", "complete", None
    if raw_status == "not_started":
        return "Ej påbörjad", "not_started", None
    if needs_review:
        return "Påbörjad", "in_progress", "Behöver granskas igen"
    return "Påbörjad", "in_progress", None


def _group_requirement_label(group: dict[str, Any]) -> str:
    requirements = list(group.get("requirements") or [])
    primary_id = group.get("primary_requirement_id")
    primary_requirement = None
    if primary_id is not None:
        primary_requirement = next((req for req in requirements if int(req.get("dietary_type_id") or 0) == int(primary_id)), None)
    label = str(group.get("label") or "").strip()
    if not label and primary_requirement:
        label = str(primary_requirement.get("name") or "").strip()
    if not label and requirements:
        label = str(requirements[0].get("name") or "").strip()
    modifiers: list[str] = []
    for requirement in requirements:
        if primary_requirement and int(requirement.get("dietary_type_id") or 0) == int(primary_requirement.get("dietary_type_id") or 0):
            continue
        requirement_name = str(requirement.get("name") or "").strip()
        if requirement_name:
            modifiers.append(requirement_name)
    if modifiers:
        if label:
            label = f"{label} · {' + '.join(modifiers)}"
        else:
            label = " + ".join(modifiers)
    return label or str(group.get("id") or "").strip()


def _presentation_requirement_group(group: dict[str, Any]) -> dict[str, Any]:
    requirements = list(group.get("requirements") or [])
    primary_id = group.get("primary_requirement_id")
    primary_requirement = None
    if primary_id is not None:
        primary_requirement = next((req for req in requirements if int(req.get("dietary_type_id") or 0) == int(primary_id)), None)

    primary_label = ""
    if primary_requirement:
        primary_label = str(primary_requirement.get("name") or "").strip()
    if not primary_label:
        primary_label = str(group.get("label") or "").strip()
    if not primary_label and requirements:
        primary_label = str(requirements[0].get("name") or "").strip()

    secondary_names: list[str] = []
    seen_names: set[str] = set()
    for requirement in requirements:
        requirement_name = str(requirement.get("name") or "").strip()
        if not requirement_name or requirement_name == primary_label or requirement_name in seen_names:
            continue
        seen_names.add(requirement_name)
        secondary_names.append(requirement_name)

    return {
        "label": primary_label,
        "secondary_label": " · ".join(secondary_names) if secondary_names else None,
    }


def _current_effective_resident_count(department_id: str, year: int, week: int) -> int:
    effective = get_effective_residents_for_week(department_id, year, week)
    lunch = effective.get("residents_lunch")
    if lunch is not None:
        return int(lunch)
    dinner = effective.get("residents_dinner")
    if dinner is not None:
        return int(dinner)
    return int(effective.get("resident_count_fixed") or 0)


def build_department_home_payload(scope: DepartmentPortalScope) -> dict[str, Any]:
    today = _date.today()
    current_year, current_week, _ = today.isocalendar()
    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT d.id, d.name, COALESCE(r.name, '') AS residence_name, d.site_id "
                "FROM departments d LEFT JOIN residences r ON r.id = d.residence_id WHERE d.id=:department_id"
            ),
            {"department_id": scope.department_id},
        ).fetchone()
        if not row:
            raise ValueError("department_not_found")
        department_id = str(row[0])
        department_name = str(row[1] or "").strip()
        residence_name = str(row[2] or "").strip()
        site_id = str(row[3] or "").strip() or scope.site_id

        department_context = {
            "resident_count": _current_effective_resident_count(department_id, int(current_year), int(current_week)),
            "requirement_groups": [],
            "service_addons": [],
        }

        requirement_groups = []
        for group in DepartmentRequirementGroupsRepo().list_for_department(department_id):
            presentation = _presentation_requirement_group(group)
            quantity = int(group.get("default_quantity") or 0)
            if quantity <= 0:
                continue
            requirement_groups.append(
                {
                    "label": presentation["label"],
                    "secondary_label": presentation["secondary_label"],
                    "quantity": quantity,
                }
            )

        service_addons: list[dict[str, Any]] = []
        for addon in DepartmentServiceAddonsRepo().list_for_department(department_id, site_id=site_id):
            count = addon.get("lunch_count")
            if count is None:
                count = addon.get("dinner_count")
            count_i = int(count or 0)
            if count_i <= 0:
                continue
            note = str(addon.get("note") or "").strip()
            service_addons.append(
                {
                    "label": str(addon.get("addon_name") or "").strip(),
                    "count": count_i,
                    "note": note,
                }
            )

        weeks: list[dict[str, Any]] = []
        publication_service = CommunBuilderPublicationService()
        status_service = DepartmentPortalWeekSubmissionService()
        rows = db.execute(
            text(
                "SELECT year, week FROM commun_builder_publication_pins "
                "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                "ORDER BY year ASC, week ASC"
            ),
            {"tenant_id": int(scope.tenant_id), "site_id": site_id},
        ).fetchall()
        for year_raw, week_raw in rows:
            year = int(year_raw)
            week = int(week_raw)
            week_start, week_end = _week_date_bounds(year, week)
            if week_end < today:
                continue
            publication = publication_service.get_publication_for_week(tenant_id=int(scope.tenant_id), site_id=site_id, year=year, week=week)
            if publication is None:
                continue
            status = status_service.get_status(scope, year, week)
            status_text, status_class, review_text = _format_choice_status(status)
            if status_class == "complete":
                action_text = "Visa"
            elif status_class == "not_started":
                action_text = "Börja"
            elif review_text:
                action_text = "Granska igen"
            else:
                action_text = "Fortsätt"
            weeks.append(
                {
                    "year": year,
                    "week": week,
                    "span": _week_span_label(year, week),
                    "status_text": status_text,
                    "status_class": status_class,
                    "review_text": review_text,
                    "action_text": action_text,
                    "url": f"/ui/portal/department/week?year={year}&week={week}",
                    "submission_status": status,
                }
            )

        return {
            "department": {
                "id": department_id,
                "name": department_name,
                "residence_name": residence_name,
            },
            "context": department_context,
            "requirement_groups": requirement_groups,
            "service_addons": service_addons,
            "weeks": weeks,
        }
    finally:
        db.close()


__all__ = ["build_department_home_payload"]