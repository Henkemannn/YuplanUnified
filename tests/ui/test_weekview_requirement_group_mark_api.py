from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from core.admin_repo import DietTypesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection
from core.db import get_session
from core.weekview.repo import WeekviewRepo
from core.weekview.service import WeekviewService


def _enable_weekview_feature(app) -> None:
    if not app.feature_registry.has("ff.weekview.enabled"):
        app.feature_registry.add("ff.weekview.enabled")
    app.feature_registry.set("ff.weekview.enabled", True)


def _seed_site_department_group(*, site_id: str, department_id: str) -> str:
    db = get_session()
    try:
        db.execute(
            text("INSERT INTO sites(id, tenant_id, name) VALUES(:id, 1, :name) ON CONFLICT(id) DO UPDATE SET tenant_id=1, name=excluded.name"),
            {"id": site_id, "name": "Site"},
        )
        db.execute(
            text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) VALUES(:id, :site_id, :name, 'fixed', 10) ON CONFLICT(id) DO UPDATE SET site_id=excluded.site_id, name=excluded.name, resident_count_mode='fixed', resident_count_fixed=10"
            ),
            {"id": department_id, "site_id": site_id, "name": "Department"},
        )
        db.commit()
    finally:
        db.close()

    diet_repo = DietTypesRepo()
    timbal_id = diet_repo.create(site_id=site_id, name="Timbal", default_select=False, semantics="atomic")
    lactose_id = diet_repo.create(site_id=site_id, name="Laktosfri", default_select=False, semantics="atomic")
    group = DepartmentRequirementGroupsRepo().create_group(department_id, 1, [timbal_id, lactose_id], label="Timbal + Laktosfri", primary_requirement_id=timbal_id)
    return str(group["id"])


def _seed_version(tenant_id: int, department_id: str, year: int, week: int, version: int) -> None:
    WeekviewRepo().get_version(tenant_id, year, week, department_id)
    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                VALUES(:tenant_id, :department_id, :year, :week, :version)
                ON CONFLICT(tenant_id, department_id, year, week) DO UPDATE SET version=excluded.version
                """
            ),
            {"tenant_id": str(tenant_id), "department_id": department_id, "year": year, "week": week, "version": version},
        )
        db.commit()
    finally:
        db.close()


def _current_etag(client, department_id: str, year: int, week: int, site_id: str) -> str:
    resp = client.get(
        f"/api/weekview/etag?department_id={department_id}&year={year}&week={week}&site_id={site_id}",
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    return str(resp.get_json()["etag"])


def _weekview_registrations_count(department_id: str, year: int, week: int) -> int:
    db = get_session()
    try:
        return int(
            db.execute(
                text("SELECT COUNT(*) FROM weekview_registrations WHERE department_id=:dep AND year=:yy AND week=:ww"),
                {"dep": department_id, "yy": year, "ww": week},
            ).scalar_one()
        )
    finally:
        db.close()


def _login(client, *, site_id: str, role: str = "cook") -> None:
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["role"] = role
        sess["user_id"] = 1


def _unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def test_requirement_group_mark_success_clear_projection_and_no_dual_write(app_session):
    app = app_session
    _enable_weekview_feature(app)
    client = app.test_client()
    site_id = _unique_id("site-cohort-mark-success")
    department_id = _unique_id("dept-cohort-mark-success")
    year = 2026
    week = 39

    with app.app_context():
        group_id = _seed_site_department_group(site_id=site_id, department_id=department_id)
        _seed_version(1, department_id, year, week, 0)

    _login(client, site_id=site_id, role="cook")
    etag_before = _current_etag(client, department_id, year, week, site_id)
    before_rows = _weekview_registrations_count(department_id, year, week)

    payload = {
        "site_id": site_id,
        "department_id": department_id,
        "year": year,
        "week": week,
        "group_id": group_id,
        "service_date": date.fromisocalendar(year, week, 1).isoformat(),
        "meal": "lunch",
        "marked": True,
    }
    resp = client.post("/api/weekview/requirement-groups/mark", json=payload, headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": etag_before})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
    assert resp.get_json()["marked"] is True
    etag_after = resp.headers.get("ETag")
    assert etag_after and etag_after != etag_before
    assert _weekview_registrations_count(department_id, year, week) == before_rows
    assert WeekviewRepo().get_version(1, year, week, department_id) == 1
    completion = DepartmentRequirementGroupCompletionRepo().get(group_id, date.fromisocalendar(year, week, 1), "lunch")
    assert completion and completion["marked"] is True

    projection = build_department_requirement_group_weekview_projection(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        service_date=date.fromisocalendar(year, week, 1),
        meal_key="lunch",
    )
    assert projection.needs[0].marked is True

    clear_resp = client.post("/api/weekview/requirement-groups/mark", json={**payload, "marked": False}, headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": etag_after})
    assert clear_resp.status_code == 200
    assert clear_resp.headers.get("ETag") and clear_resp.headers.get("ETag") != etag_after
    assert WeekviewRepo().get_version(1, year, week, department_id) == 2
    cleared = DepartmentRequirementGroupCompletionRepo().get(group_id, date.fromisocalendar(year, week, 1), "lunch")
    assert cleared and cleared["marked"] is False
    cleared_projection = build_department_requirement_group_weekview_projection(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        service_date=date.fromisocalendar(year, week, 1),
        meal_key="lunch",
    )
    assert cleared_projection.needs[0].marked is False


@pytest.mark.parametrize(
    "override, expected_title, include_if_match, expected_status",
    [
        ({"meal": "breakfast"}, "invalid_meal", True, 400),
        ({"service_date": "not-a-date"}, "invalid_service_date", True, 400),
        ({"service_date": "2026-09-28"}, "service_date_out_of_week", True, 400),
        ({}, "missing_if_match", False, 428),
    ],
)
def test_requirement_group_mark_validation_rejects_invalid_payloads(app_session, override, expected_title, include_if_match, expected_status):
    app = app_session
    _enable_weekview_feature(app)
    client = app.test_client()
    site_id = _unique_id("site-cohort-mark-validation")
    department_id = _unique_id("dept-cohort-mark-validation")
    year = 2026
    week = 39

    with app.app_context():
        group_id = _seed_site_department_group(site_id=site_id, department_id=department_id)
        _seed_version(1, department_id, year, week, 0)

    _login(client, site_id=site_id, role="cook")
    payload = {
        "site_id": site_id,
        "department_id": department_id,
        "year": year,
        "week": week,
        "group_id": group_id,
        "service_date": date.fromisocalendar(year, week, 1).isoformat(),
        "meal": "lunch",
        "marked": True,
    }
    payload.update(override)
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    if include_if_match:
        headers["If-Match"] = _current_etag(client, department_id, year, week, site_id)
    resp = client.post("/api/weekview/requirement-groups/mark", json=payload, headers=headers)
    assert resp.status_code == expected_status
    assert expected_title in resp.get_json()["title"]


def test_requirement_group_mark_wrong_group_department_site_rejected(app_session):
    app = app_session
    _enable_weekview_feature(app)
    client = app.test_client()
    site_a = _unique_id("site-cohort-mark-a")
    site_b = _unique_id("site-cohort-mark-b")
    dept_a = _unique_id("dept-cohort-mark-a")
    dept_b = _unique_id("dept-cohort-mark-b")
    year = 2026
    week = 39

    with app.app_context():
        group_a = _seed_site_department_group(site_id=site_a, department_id=dept_a)
        group_b = _seed_site_department_group(site_id=site_b, department_id=dept_b)
        _seed_version(1, dept_a, year, week, 0)
        _seed_version(1, dept_b, year, week, 0)

    _login(client, site_id=site_a, role="cook")
    etag = _current_etag(client, dept_a, year, week, site_a)
    base_payload = {
        "site_id": site_a,
        "department_id": dept_a,
        "year": year,
        "week": week,
        "group_id": group_a,
        "service_date": date.fromisocalendar(year, week, 1).isoformat(),
        "meal": "lunch",
        "marked": True,
    }

    wrong_group = client.post(
        "/api/weekview/requirement-groups/mark",
        json={**base_payload, "group_id": group_b},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": etag},
    )
    assert wrong_group.status_code == 403

    wrong_site = client.post(
        "/api/weekview/requirement-groups/mark",
        json={**base_payload, "site_id": site_b},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": etag},
    )
    assert wrong_site.status_code == 403

    wrong_department = client.post(
        "/api/weekview/requirement-groups/mark",
        json={**base_payload, "department_id": dept_b, "group_id": group_b, "site_id": site_b},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": etag},
    )
    assert wrong_department.status_code == 403


def test_requirement_group_mark_stale_etag_and_cas_collision_reject_without_mutating(app_session, monkeypatch):
    app = app_session
    _enable_weekview_feature(app)
    client = app.test_client()
    site_id = _unique_id("site-cohort-mark-stale")
    department_id = _unique_id("dept-cohort-mark-stale")
    year = 2026
    week = 39

    with app.app_context():
        group_id = _seed_site_department_group(site_id=site_id, department_id=department_id)
        _seed_version(1, department_id, year, week, 1)

    _login(client, site_id=site_id, role="cook")
    stale_etag = WeekviewService().build_etag(1, department_id, year, week, 0)
    payload = {
        "site_id": site_id,
        "department_id": department_id,
        "year": year,
        "week": week,
        "group_id": group_id,
        "service_date": date.fromisocalendar(year, week, 1).isoformat(),
        "meal": "lunch",
        "marked": True,
    }
    stale_resp = client.post("/api/weekview/requirement-groups/mark", json=payload, headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": stale_etag})
    assert stale_resp.status_code == 412
    assert WeekviewRepo().get_version(1, year, week, department_id) == 1
    assert DepartmentRequirementGroupCompletionRepo().get(group_id, date.fromisocalendar(year, week, 1), "lunch") is None

    def _collision(*args, **kwargs):
        return None

    monkeypatch.setattr(WeekviewRepo, "compare_and_bump_version_in_session", _collision)
    fresh_etag = _current_etag(client, department_id, year, week, site_id)
    collision_resp = client.post("/api/weekview/requirement-groups/mark", json=payload, headers={"X-User-Role": "cook", "X-Tenant-Id": "1", "If-Match": fresh_etag})
    assert collision_resp.status_code == 412
    assert WeekviewRepo().get_version(1, year, week, department_id) == 1
    assert DepartmentRequirementGroupCompletionRepo().get(group_id, date.fromisocalendar(year, week, 1), "lunch") is None
