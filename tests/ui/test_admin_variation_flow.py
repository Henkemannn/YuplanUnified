from __future__ import annotations

from datetime import date, timedelta
import uuid

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.residents_schedule_repo import ResidentsScheduleRepo
from core.db import get_session
from sqlalchemy import text


def _headers():
    return {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _current_week():
    iso = date.today().isocalendar()
    return iso[0], iso[1]


def _seed_department_with_need(*, resident_count: int = 12, default_quantity: int = 2):
    site, _ = SitesRepo().create_site(f"Variation flow site {uuid.uuid4()}")
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name=f"Avd Variation {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    DepartmentsRepo().upsert_department_diet_defaults(
        dept["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": default_quantity},
            {"diet_type_id": glutenfri_id, "default_count": default_quantity},
        ],
    )
    group = DepartmentRequirementGroupsRepo().create_group(
        dept["id"],
        default_quantity,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )
    return site, dept, group


def _resident_form(*, year: int, week: int, changes: dict[tuple[int, str], int], default: int = 12) -> dict[str, str]:
    payload: dict[str, str] = {"selected_year": str(year), "selected_week": str(week), "mode": "week"}
    for weekday in range(1, 8):
        for meal in ("lunch", "dinner"):
            payload[f"day_{weekday}_{meal}"] = str(changes.get((weekday, meal), default))
    return payload


def _need_payload(group_id: str, *, year: int, week: int, changes: dict[tuple[int, str], int | None], mode: str = "week") -> dict[str, str]:
    payload: dict[str, str] = {"selected_year": str(year), "selected_week": str(week), "mode": mode}
    for (weekday, meal), value in changes.items():
        payload[f"need_day_{group_id}_{weekday}_{meal}"] = "" if value is None else str(value)
    return payload


def test_resident_variation_only_keeps_need_unchanged(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _resident_form(year=year, week=week, changes={(2, "lunch"): 11})
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    rows = ResidentsScheduleRepo().get_week(dept["id"], week)
    resident_map = {(int(row["weekday"]), str(row["meal"])): int(row["count"]) for row in rows}
    assert resident_map[(2, "lunch")] == 11
    assert DepartmentRequirementGroupServiceOverridesRepo().list_for_group(group["id"]) == []
    assert DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group["id"]) == []


def test_resident_and_need_variation_save_together(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _resident_form(year=year, week=week, changes={(2, "lunch"): 11})
    payload.update(_need_payload(group["id"], year=year, week=week, changes={(2, "lunch"): 1}))
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    rows = ResidentsScheduleRepo().get_week(dept["id"], week)
    resident_map = {(int(row["weekday"]), str(row["meal"])): int(row["count"]) for row in rows}
    assert resident_map[(2, "lunch")] == 11
    override_repo = DepartmentRequirementGroupServiceOverridesRepo()
    monday = date.fromisocalendar(year, week, 1)
    tuesday = date.fromisocalendar(year, week, 2)
    assert override_repo.get_override(group["id"], tuesday, "lunch") is not None
    assert override_repo.resolve_effective_quantity(group["id"], tuesday, "lunch") == 1
    assert override_repo.resolve_effective_quantity(group["id"], monday, "lunch") == 2


def test_need_variation_only_keeps_residents_unchanged(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _need_payload(group["id"], year=year, week=week, changes={(2, "lunch"): 1})
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    assert ResidentsScheduleRepo().get_week(dept["id"], week) == []
    override_repo = DepartmentRequirementGroupServiceOverridesRepo()
    tuesday = date.fromisocalendar(year, week, 2)
    assert override_repo.resolve_effective_quantity(group["id"], tuesday, "lunch") == 1


def test_week_only_need_variation_writes_exact_date_overrides(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _need_payload(group["id"], year=year, week=week, changes={(1, "lunch"): 3, (2, "dinner"): 0}, mode="week")
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
    monday = date.fromisocalendar(year, week, 1)
    tuesday = date.fromisocalendar(year, week, 2)
    assert exact_repo.get_override(group["id"], monday, "lunch") is not None
    assert exact_repo.resolve_effective_quantity(group["id"], monday, "lunch") == 3
    assert exact_repo.get_override(group["id"], tuesday, "dinner") is not None
    assert exact_repo.resolve_effective_quantity(group["id"], tuesday, "dinner") == 0


def test_forever_need_variation_writes_weekday_overrides(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _need_payload(group["id"], year=year, week=week, changes={(4, "lunch"): 1, (4, "dinner"): 0}, mode="forever")
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    assert weekday_repo.get_override(group["id"], 4, "lunch") is not None
    assert weekday_repo.resolve_effective_quantity(group["id"], 4, "lunch", 2) == 1
    assert weekday_repo.resolve_effective_quantity(group["id"], 4, "dinner", 2) == 0


def test_unrelated_requirement_overrides_remain_unchanged(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    other_exact_date = date.fromisocalendar(year, week, 6) + timedelta(days=10)
    exact_repo.set_override(group["id"], other_exact_date, "lunch", 5)
    weekday_repo.set_override(group["id"], 3, "dinner", 4)

    payload = _need_payload(group["id"], year=year, week=week, changes={(1, "lunch"): 3}, mode="week")
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    assert exact_repo.resolve_effective_quantity(group["id"], other_exact_date, "lunch") == 5
    assert weekday_repo.resolve_effective_quantity(group["id"], 3, "dinner", 2) == 4


def test_impossible_state_rejected(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=10)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _resident_form(year=year, week=week, changes={(1, "lunch"): 9})
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert ResidentsScheduleRepo().get_week(dept["id"], week) == []
    override_repo = DepartmentRequirementGroupServiceOverridesRepo()
    monday = date.fromisocalendar(year, week, 1)
    assert override_repo.resolve_effective_quantity(group["id"], monday, "lunch") == 10


def test_negative_quantities_are_rejected(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _need_payload(group["id"], year=year, week=week, changes={(1, "lunch"): -1}, mode="week")
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert DepartmentRequirementGroupServiceOverridesRepo().list_for_group(group["id"]) == []
    assert DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group["id"]) == []


def test_resident_only_submission_remains_compatible(client_admin):
    site, dept, group = _seed_department_with_need(resident_count=12, default_quantity=2)
    year, week = _current_week()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    payload = _resident_form(year=year, week=week, changes={(2, "lunch"): 11, (2, "dinner"): 11})
    resp = client_admin.post(f"/ui/admin/departments/{dept['id']}/variation", data=payload, headers=_headers(), follow_redirects=False)
    assert resp.status_code in (302, 303)

    rows = ResidentsScheduleRepo().get_week(dept["id"], week)
    resident_map = {(int(row["weekday"]), str(row["meal"])): int(row["count"]) for row in rows}
    assert resident_map[(2, "lunch")] == 11
    assert resident_map[(2, "dinner")] == 11
    assert DepartmentRequirementGroupServiceOverridesRepo().list_for_group(group["id"]) == []
