from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.csrf import CSRF_SESSION_KEY
from core.db import get_session
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.planera_product2_page3_vm import Product2Page3CompletionTargetVM
from core.weekview.cohort_bulk_completion_service import WeekviewCohortBulkCompletionService
from core.weekview.repo import WeekviewRepo
from core.weekview.service import WeekviewService


def _enable_planera_feature(app) -> None:
    reg = getattr(app, "feature_registry", None)
    if reg is None:
        return
    if not reg.has("ff.planera.enabled"):
        reg.add("ff.planera.enabled")
    reg.set("ff.planera.enabled", True)


def _login(client, *, site_id: str, role: str = "cook") -> None:
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
        sess["role"] = role
        sess["user_id"] = 1


def _csrf_headers(client, token: str = "planera-test-csrf") -> dict[str, str]:
    with client.session_transaction() as sess:
        sess[CSRF_SESSION_KEY] = token
    return {"X-CSRF-Token": token}


def _seed_site_with_two_departments(app) -> dict[str, str]:
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    diet_repo = DietTypesRepo()
    group_repo = DepartmentRequirementGroupsRepo()

    site, _ = site_repo.create_site(f"Product2 completion {uuid4().hex[:8]}")
    dept_a, _ = dept_repo.create_department(site["id"], f"Dept A {uuid4().hex[:8]}", "fixed", 10)
    dept_b, _ = dept_repo.create_department(site["id"], f"Dept B {uuid4().hex[:8]}", "fixed", 8)

    with app.app_context():
        req_a = diet_repo.create(site_id=site["id"], name=f"Req A {uuid4().hex[:8]}", default_select=False, semantics="atomic")
        req_b = diet_repo.create(site_id=site["id"], name=f"Req B {uuid4().hex[:8]}", default_select=False, semantics="atomic")

    group_a = group_repo.create_group(dept_a["id"], 1, [req_a], label="Group A", primary_requirement_id=req_a)
    group_b = group_repo.create_group(dept_b["id"], 1, [req_b], label="Group B", primary_requirement_id=req_b)
    return {
        "site_id": site["id"],
        "dept_a": dept_a["id"],
        "dept_b": dept_b["id"],
        "group_a": str(group_a["id"]),
        "group_b": str(group_b["id"]),
    }


def _seed_weekview_version(tenant_id: int, department_id: str, year: int, week: int, version: int) -> None:
    WeekviewRepo().get_version(tenant_id, year, week, department_id)
    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                VALUES(:tenant_id, :department_id, :year, :week, :version)
                ON CONFLICT(tenant_id, department_id, year, week)
                DO UPDATE SET version=excluded.version
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "department_id": department_id,
                "year": year,
                "week": week,
                "version": version,
            },
        )
        db.commit()
    finally:
        db.close()


def _ensure_weekview_registrations_table() -> None:
    db = get_session()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS weekview_registrations (
                  tenant_id TEXT NOT NULL,
                  department_id TEXT NOT NULL,
                  year INTEGER NOT NULL,
                  week INTEGER NOT NULL,
                  day_of_week INTEGER NOT NULL,
                  meal TEXT NOT NULL,
                  diet_type TEXT NOT NULL,
                  marked INTEGER NOT NULL DEFAULT 0,
                  UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
                )
                """
            )
        )
        db.commit()
    finally:
        db.close()


def _current_etag(department_id: str, year: int, week: int, site_id: str) -> str:
    service = WeekviewService()
    version = service.get_effective_version(1, year, week, department_id, site_id)
    return service.build_etag(1, department_id, year, week, version)


def _count_weekview_registrations(department_id: str, year: int, week: int) -> int:
    db = get_session()
    try:
        row = db.execute(
            text("SELECT COUNT(*) FROM weekview_registrations WHERE department_id=:dep AND year=:yy AND week=:ww"),
            {"dep": department_id, "yy": year, "ww": week},
        ).fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        db.close()


def _seed_weekview_registration_marker(department_id: str, year: int, week: int) -> None:
    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO weekview_registrations(
                    tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked
                ) VALUES('1', :dep, :yy, :ww, 1, 'lunch', 'marker', 1)
                """
            ),
            {"dep": department_id, "yy": year, "ww": week},
        )
        db.commit()
    finally:
        db.close()


def _make_vm(captured: dict[str, object], *, site_id: str, service_date: date, meal: str, ready: bool, blockers: tuple[str, ...], targets: tuple[Product2Page3CompletionTargetVM, ...]):
    def _builder(*, tenant_id, site_id: str, service_date: date, meal: str, view=None, special_view=None):
        captured["args"] = {
            "tenant_id": tenant_id,
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": meal,
            "view": view,
            "special_view": special_view,
        }
        return SimpleNamespace(
            ready=ready,
            blockers=blockers,
            completion_targets=targets,
        )

    return _builder


def test_product2_production_completion_marks_and_clears_targets(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    _ensure_weekview_registrations_table()
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)
        _seed_weekview_registration_marker(dept_a, year, week)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm(captured, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )
    monkeypatch.setattr(
        WeekviewRepo,
        "apply_operations",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected apply_operations")),
    )
    monkeypatch.setattr(
        WeekviewService,
        "toggle_marks",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected toggle_marks")),
    )

    _login(client, site_id=site_id, role="cook")
    payload = {
        "site_id": site_id,
        "service_date": service_date.isoformat(),
        "meal": "lunch",
        "marked": True,
        "expected_etags": {
            dept_a: _current_etag(dept_a, year, week, site_id),
            dept_b: _current_etag(dept_b, year, week, site_id),
        },
        "completion_targets": ["client-supplied-targets-are-ignored"],
        "group_id": "client-supplied-group-id",
        "requirement_group_id": "client-supplied-requirement-group-id",
        "combination_key": "client-supplied-combination-key",
        "diet_type_id": "client-supplied-diet-type-id",
    }

    before_rows = _count_weekview_registrations(dept_a, year, week) + _count_weekview_registrations(dept_b, year, week)
    response = client.post("/api/planera/product2/production-completion", json=payload, headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["marked"] is True
    assert body["target_count"] == 2
    assert set(body["departments"]) == {dept_a, dept_b}
    assert set(body["department_etags"]) == {dept_a, dept_b}
    assert body["department_etags"][dept_a] != payload["expected_etags"][dept_a]
    assert body["department_etags"][dept_b] != payload["expected_etags"][dept_b]
    assert _count_weekview_registrations(dept_a, year, week) + _count_weekview_registrations(dept_b, year, week) == before_rows
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 1
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 1

    completion_a = DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch")
    completion_b = DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch")
    assert completion_a and completion_a["marked"] is True
    assert completion_b and completion_b["marked"] is True

    clear_payload = {
        "site_id": site_id,
        "service_date": service_date.isoformat(),
        "meal": "lunch",
        "marked": False,
        "expected_etags": {
            dept_a: body["departments"][dept_a]["etag"],
            dept_b: body["departments"][dept_b]["etag"],
        },
    }
    clear_response = client.post("/api/planera/product2/production-completion", json=clear_payload, headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert clear_response.status_code == 200
    clear_body = clear_response.get_json()
    assert clear_body["marked"] is False
    assert clear_body["target_count"] == 2
    assert set(clear_body["department_etags"]) == {dept_a, dept_b}
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 2
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 2
    cleared_a = DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch")
    cleared_b = DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch")
    assert cleared_a and cleared_a["marked"] is False
    assert cleared_b and cleared_b["marked"] is False
    assert captured["args"]["site_id"] == site_id
    assert captured["args"]["service_date"] == service_date.isoformat()
    assert captured["args"]["meal"] == "lunch"

    repeat_response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": payload["expected_etags"],
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert repeat_response.status_code == 412
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 2
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 2
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch").get("marked") is False
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch").get("marked") is False


def test_product2_production_completion_rejects_missing_department_etag_without_mutating(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    _ensure_weekview_registrations_table()
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {
                dept_a: _current_etag(dept_a, year, week, site_id),
            },
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 412
    assert response.get_json()["title"] == "etag_mismatch"
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_rejects_stale_department_etag_without_mutating(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    _ensure_weekview_registrations_table()
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {
                dept_a: 'W/"weekview:dept:{}:year:2026:week:39:v99"'.format(dept_a),
                dept_b: _current_etag(dept_b, year, week, site_id),
            },
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 412
    assert response.get_json()["title"] == "etag_mismatch"
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_rejects_when_page_is_not_ready(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    _ensure_weekview_registrations_table()
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=False, blockers=("UNREVIEWED_OPTIONS",), targets=targets),
    )

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {
                dept_a: _current_etag(dept_a, year, week, site_id),
                dept_b: _current_etag(dept_b, year, week, site_id),
            },
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["title"] == "production_not_ready"
    assert "UNREVIEWED_OPTIONS" in body["blockers"]
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_rejects_no_completion_targets(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=()),
    )

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={"site_id": site_id, "service_date": service_date.isoformat(), "meal": "lunch", "marked": True},
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["title"] == "no_completion_targets"
    assert body["target_count"] == 0
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0


@pytest.mark.parametrize(
    "payload_override, expected_detail, expected_status",
    [
        ({}, "invalid_marked", 400),
        ({"marked": "true"}, "invalid_marked", 400),
        ({"marked": 1}, "invalid_marked", 400),
        ({"marked": None}, "invalid_marked", 400),
        ({"marked": True, "expected_etags": []}, "invalid_expected_etags", 400),
    ],
)
def test_product2_production_completion_rejects_invalid_marked_and_etag_shape(app_session, client_admin, monkeypatch, payload_override, expected_detail, expected_status):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    _login(client, site_id=site_id, role="cook")
    payload = {"site_id": site_id, "service_date": service_date.isoformat(), "meal": "lunch"}
    payload.update(payload_override)
    if payload.get("marked", True) is True and "expected_etags" not in payload:
        payload["expected_etags"] = {
            dept_a: _current_etag(dept_a, year, week, site_id),
            dept_b: _current_etag(dept_b, year, week, site_id),
        }

    response = client.post(
        "/api/planera/product2/production-completion",
        json=payload,
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == expected_status
    body = response.get_json()
    assert body["title"] == "Bad Request"
    assert body["detail"] == expected_detail
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_rejects_invalid_site_and_active_site_mismatch(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)
        other_site, _ = SitesRepo().create_site(f"Other site {uuid4().hex[:8]}")

    site_id = seeded["site_id"]
    other_site_id = other_site["id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    _login(client, site_id="00000000-0000-0000-0000-000000000000", role="cook")
    bad_site_response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": "00000000-0000-0000-0000-000000000000",
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {dept_a: _current_etag(dept_a, year, week, site_id), dept_b: _current_etag(dept_b, year, week, site_id)},
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert bad_site_response.status_code == 404
    assert bad_site_response.get_json()["title"] == "Not Found"
    assert bad_site_response.get_json()["detail"] == "site_or_department_not_found"

    _login(client, site_id=site_id, role="cook")
    mismatch_response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": other_site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {dept_a: _current_etag(dept_a, year, week, site_id), dept_b: _current_etag(dept_b, year, week, site_id)},
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert mismatch_response.status_code == 403
    assert mismatch_response.get_json()["title"] == "site_mismatch"


@pytest.mark.parametrize(
    "expected_etags, expected_status, expected_title",
    [
        (None, 400, "invalid_expected_etags"),
        ({"unexpected": 'W/"weekview:dept:unexpected:year:2026:week:39:v0"'}, 412, "etag_mismatch"),
        ({"missing-one": 'W/"weekview:dept:missing-one:year:2026:week:39:v0"'}, 412, "etag_mismatch"),
        ({"stale-first": 'W/"weekview:dept:stale-first:year:2026:week:39:v0"'}, 412, "etag_mismatch"),
        ({"stale-later": 'W/"weekview:dept:stale-later:year:2026:week:39:v0"'}, 412, "etag_mismatch"),
    ],
)
def test_product2_production_completion_rejects_expected_etag_set_errors(app_session, client_admin, monkeypatch, expected_etags, expected_status, expected_title):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    _login(client, site_id=site_id, role="cook")
    payload = {
        "site_id": site_id,
        "service_date": service_date.isoformat(),
        "meal": "lunch",
        "marked": True,
        "expected_etags": expected_etags,
    }
    if expected_etags and "missing-one" in expected_etags:
        payload["expected_etags"] = {dept_a: _current_etag(dept_a, year, week, site_id)}
    elif expected_etags and "stale-first" in expected_etags:
        payload["expected_etags"] = {
            dept_a: 'W/"weekview:dept:{}:year:2026:week:39:v9"'.format(dept_a),
            dept_b: _current_etag(dept_b, year, week, site_id),
        }
    elif expected_etags and "stale-later" in expected_etags:
        payload["expected_etags"] = {
            dept_a: _current_etag(dept_a, year, week, site_id),
            dept_b: 'W/"weekview:dept:{}:year:2026:week:39:v9"'.format(dept_b),
        }
    elif expected_etags is not None and "unexpected" in expected_etags:
        payload["expected_etags"] = {
            dept_a: _current_etag(dept_a, year, week, site_id),
            dept_b: _current_etag(dept_b, year, week, site_id),
            "unexpected": expected_etags["unexpected"],
        }
    else:
        payload.pop("expected_etags")

    response = client.post(
        "/api/planera/product2/production-completion",
        json=payload,
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == expected_status
    body = response.get_json()
    assert body["title"] == ("Bad Request" if expected_status == 400 else "etag_mismatch")
    assert body["detail"] == expected_title
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_rejects_cas_race_after_etag_validation(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    dept_b = seeded["dept_b"]
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)
        _seed_weekview_version(1, dept_b, year, week, 0)

    targets = (
        Product2Page3CompletionTargetVM(requirement_group_id=group_a, destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
        Product2Page3CompletionTargetVM(requirement_group_id=group_b, destination_id=dept_b, service_date=service_date.isoformat(), meal="lunch", quantity=1),
    )
    monkeypatch.setattr(
        "core.planera_api.build_product2_page3_vm",
        _make_vm({}, site_id=site_id, service_date=service_date, meal="lunch", ready=True, blockers=(), targets=targets),
    )

    original_compare = WeekviewRepo.compare_and_bump_version_in_session

    def _collision_once(self, db, *, tenant_id, year, week, department_id, expected_version):
        if department_id == dept_b:
            return None
        return original_compare(self, db, tenant_id=tenant_id, year=year, week=week, department_id=department_id, expected_version=expected_version)

    monkeypatch.setattr(WeekviewRepo, "compare_and_bump_version_in_session", _collision_once)

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {
                dept_a: _current_etag(dept_a, year, week, site_id),
                dept_b: _current_etag(dept_b, year, week, site_id),
            },
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 412
    assert response.get_json()["title"] == "etag_mismatch"
    assert WeekviewRepo().get_version(1, year, week, dept_a) == 0
    assert WeekviewRepo().get_version(1, year, week, dept_b) == 0
    assert DepartmentRequirementGroupCompletionRepo().get(group_a, service_date, "lunch") is None
    assert DepartmentRequirementGroupCompletionRepo().get(group_b, service_date, "lunch") is None


def test_product2_production_completion_captures_deterministic_separate_targets(app_session, client_admin, monkeypatch):
    app = app_session
    _enable_planera_feature(app)
    client = client_admin

    with app.app_context():
        seeded = _seed_site_with_two_departments(app)

    site_id = seeded["site_id"]
    dept_a = seeded["dept_a"]
    year = 2026
    week = 39
    service_date = date.fromisocalendar(year, week, 1)

    with app.app_context():
        _seed_weekview_version(1, dept_a, year, week, 0)

    known_group_ids = (
        "2b4a2844-5b18-42cd-895f-d3d20358fe9e",
        "6250379d-69d3-4d41-b457-2b9ad6630b0e",
    )
    target_log: dict[str, object] = {}

    def _fake_vm(*, tenant_id, site_id: str, service_date: date, meal: str, view=None, special_view=None):
        target_log["vm"] = (tenant_id, site_id, service_date.isoformat(), meal)
        return SimpleNamespace(
            ready=True,
            blockers=(),
            completion_targets=(
                Product2Page3CompletionTargetVM(requirement_group_id=known_group_ids[0], destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=1),
                Product2Page3CompletionTargetVM(requirement_group_id=known_group_ids[1], destination_id=dept_a, service_date=service_date.isoformat(), meal="lunch", quantity=2),
            ),
        )

    captured: dict[str, object] = {}

    def _fake_bulk(self, *, tenant_id, year, week, expected_base_versions, targets, marked):
        captured["tenant_id"] = tenant_id
        captured["expected_base_versions"] = dict(expected_base_versions)
        captured["targets"] = tuple(targets)
        captured["marked"] = marked
        return {"marked": marked, "target_count": len(tuple(targets)), "departments": {dept_a: 1}}

    monkeypatch.setattr("core.planera_api.build_product2_page3_vm", _fake_vm)
    monkeypatch.setattr(WeekviewCohortBulkCompletionService, "set_marked_many_with_weekview_versions", _fake_bulk)

    _login(client, site_id=site_id, role="cook")
    response = client.post(
        "/api/planera/product2/production-completion",
        json={
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": "lunch",
            "marked": True,
            "expected_etags": {dept_a: _current_etag(dept_a, year, week, site_id)},
            "completion_targets": ["client-cannot-control-identity"],
            "group_id": "client-group-id",
            "requirement_group_id": "client-requirement-group-id",
            "combination_key": "client-combination-key",
            "diet_type_id": "client-diet-type-id",
        },
        headers={**_csrf_headers(client), "X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["target_count"] == 2
    assert [target.group_id for target in captured["targets"]] == list(known_group_ids)
    assert all(target.department_id == dept_a for target in captured["targets"])
    assert captured["marked"] is True
    assert captured["expected_base_versions"] == {dept_a: 0}