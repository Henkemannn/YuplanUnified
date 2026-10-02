from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from core.db import get_session
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from portal.department.auth import DepartmentPortalScope
from portal.department.submission_service import DepartmentPortalWeekSubmissionService


YEAR = 2026
WEEK = 40
SITE_ID = "portal-submission-site"


def _h():
    return {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _scope(dept_id: str, site_id: str = SITE_ID) -> DepartmentPortalScope:
    return DepartmentPortalScope(user_id=1, role="admin", tenant_id=1, department_id=dept_id, site_id=site_id)


def _seed_two_day_publication(seed_canonical_builder_publication, *, site_id: str, year: int, week: int, builder_version: int = 1, alt1_name: str = "Pannbiff", alt2_name: str = "Fiskgratäng") -> None:
    seed_canonical_builder_publication(
        site_id=site_id,
        year=year,
        week=week,
        builder_version=builder_version,
        alt1_name=alt1_name,
        alt2_name=alt2_name,
        dessert_name="Fruktsallad",
        dinner_name="Kvällsgröt",
    )
    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT projection_snapshot_json FROM commun_builder_publication_pins WHERE site_id=:site_id AND year=:year AND week=:week"
            ),
            {"site_id": site_id, "year": year, "week": week},
        ).fetchone()
        assert row and row[0]
        snapshot = json.loads(row[0])
        snapshot["rows"].extend(
            [
                {
                    "day": "tuesday",
                    "meal": "lunch",
                    "variant_type": "alt1",
                    "sort_order": 1,
                    "builder_menu_row_id": f"{site_id}-tue-lunch-alt1-{builder_version}",
                    "composition_id": "builder-alt1",
                    "resolved": True,
                    "text": "Tisdag alt1",
                    "unresolved_text": None,
                    "error": None,
                },
                {
                    "day": "tuesday",
                    "meal": "lunch",
                    "variant_type": "alt2",
                    "sort_order": 2,
                    "builder_menu_row_id": f"{site_id}-tue-lunch-alt2-{builder_version}",
                    "composition_id": "builder-alt2",
                    "resolved": True,
                    "text": "Tisdag alt2",
                    "unresolved_text": None,
                    "error": None,
                },
            ]
        )
        db.execute(
            text(
                "UPDATE commun_builder_publication_pins SET projection_snapshot_json=:snapshot WHERE site_id=:site_id AND year=:year AND week=:week"
            ),
            {"snapshot": json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), "site_id": site_id, "year": year, "week": week},
        )
        db.commit()
    finally:
        db.close()


def _seed_zero_choice_publication(seed_canonical_builder_publication, *, site_id: str, year: int, week: int, builder_version: int = 1) -> None:
    seed_canonical_builder_publication(
        site_id=site_id,
        year=year,
        week=week,
        builder_version=builder_version,
        alt1_name="Pannbiff",
        alt2_name="Fiskgratäng",
        dessert_name="Fruktsallad",
        dinner_name="Kvällsgröt",
    )
    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT projection_snapshot_json FROM commun_builder_publication_pins WHERE site_id=:site_id AND year=:year AND week=:week"
            ),
            {"site_id": site_id, "year": year, "week": week},
        ).fetchone()
        assert row and row[0]
        snapshot = json.loads(row[0])
        snapshot["rows"] = [row_item for row_item in snapshot["rows"] if str(row_item.get("meal") or "") != "lunch"]
        db.execute(
            text(
                "UPDATE commun_builder_publication_pins SET projection_snapshot_json=:snapshot WHERE site_id=:site_id AND year=:year AND week=:week"
            ),
            {"snapshot": json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), "site_id": site_id, "year": year, "week": week},
        )
        db.commit()
    finally:
        db.close()


def _status(scope: DepartmentPortalScope, year: int = YEAR, week: int = WEEK):
    return DepartmentPortalWeekSubmissionService().get_status(scope, year, week)


def _submit(client, dept_id: str, year: int = YEAR, week: int = WEEK):
    return client.post(
        "/portal/department/week/submit",
        json={"year": year, "week": week},
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )


def _seed_department(seed_portal_department_data, *, dept_id: str, site_id: str = SITE_ID, year: int = YEAR, week: int = WEEK, note: str = "Inga risrätter"):
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week, note=note)


def test_unpublished_week_cannot_be_submitted(client_admin, seed_portal_department_data):
    dept_id = "portal-submission-unpublished"
    _seed_department(seed_portal_department_data, dept_id=dept_id)

    resp = _submit(client_admin, dept_id)
    assert resp.status_code == 404


def test_required_choice_status_lifecycle(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    dept_id = "portal-submission-required"
    _seed_department(seed_portal_department_data, dept_id=dept_id)
    _seed_two_day_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK)

    scope = _scope(dept_id)
    status_before = _status(scope)
    assert status_before["required_choice_count"] == 2
    assert status_before["completed_choice_count"] == 0
    assert status_before["status"] == "not_started"
    assert status_before["is_submittable"] is False
    assert status_before["has_submission"] is False

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES(1, :site_id, :dept_id, :year, :week, 1, 'lunch', 'alt1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"site_id": SITE_ID, "dept_id": dept_id, "year": YEAR, "week": WEEK},
        )
        db.commit()
    finally:
        db.close()

    status_partial = _status(scope)
    assert status_partial["completed_choice_count"] == 1
    assert status_partial["status"] == "in_progress"
    assert status_partial["is_submittable"] is False

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES(1, :site_id, :dept_id, :year, :week, 2, 'lunch', 'alt2', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"site_id": SITE_ID, "dept_id": dept_id, "year": YEAR, "week": WEEK},
        )
        db.commit()
    finally:
        db.close()

    status_ready = _status(scope)
    assert status_ready["completed_choice_count"] == 2
    assert status_ready["status"] == "in_progress"
    assert status_ready["is_submittable"] is True
    assert status_ready["has_submission"] is False

    submit_resp = _submit(client_admin, dept_id)
    assert submit_resp.status_code == 200
    status_complete = _status(scope)
    assert status_complete["status"] == "complete"
    assert status_complete["has_submission"] is True
    assert status_complete["submission_is_current"] is True
    assert status_complete["needs_review"] is False


def test_zero_choice_week_can_be_submitted(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    dept_id = "portal-submission-zero"
    _seed_department(seed_portal_department_data, dept_id=dept_id)
    _seed_zero_choice_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK)

    scope = _scope(dept_id)
    status_before = _status(scope)
    assert status_before["required_choice_count"] == 0
    assert status_before["completed_choice_count"] == 0
    assert status_before["status"] == "not_started"
    assert status_before["is_submittable"] is True

    submit_resp = _submit(client_admin, dept_id)
    assert submit_resp.status_code == 200
    status_after = _status(scope)
    assert status_after["status"] == "complete"
    assert status_after["submission_is_current"] is True


def test_choice_change_after_submit_stales_submission(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    dept_id = "portal-submission-choice-change"
    _seed_department(seed_portal_department_data, dept_id=dept_id)
    _seed_two_day_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK)
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_id, year=YEAR, week=WEEK, weekday=1, selected_variant="Alt1")
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_id, year=YEAR, week=WEEK, weekday=2, selected_variant="Alt2")

    assert _submit(client_admin, dept_id).status_code == 200
    scope = _scope(dept_id)
    status_complete = _status(scope)
    assert status_complete["status"] == "complete"

    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_id, year=YEAR, week=WEEK, weekday=2, selected_variant="Alt1")
    status_stale = _status(scope)
    assert status_stale["status"] == "in_progress"
    assert status_stale["needs_review"] is True
    assert status_stale["submission_is_current"] is False


def test_republish_after_submit_stales_then_resubmission_restores_complete(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    dept_id = "portal-submission-republish"
    _seed_department(seed_portal_department_data, dept_id=dept_id)
    _seed_two_day_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK, builder_version=1, alt1_name="Pannbiff")
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_id, year=YEAR, week=WEEK, weekday=1, selected_variant="Alt1")
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_id, year=YEAR, week=WEEK, weekday=2, selected_variant="Alt2")

    assert _submit(client_admin, dept_id).status_code == 200
    scope = _scope(dept_id)
    status_complete = _status(scope)
    assert status_complete["status"] == "complete"

    _seed_two_day_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK, builder_version=2, alt1_name="Köttbullar")
    status_stale = _status(scope)
    assert status_stale["status"] == "in_progress"
    assert status_stale["needs_review"] is True
    assert status_stale["submission_is_current"] is False
    assert status_stale["publication_builder_menu_version"] == 2

    assert _submit(client_admin, dept_id).status_code == 200
    status_resubmitted = _status(scope)
    assert status_resubmitted["status"] == "complete"
    assert status_resubmitted["needs_review"] is False
    assert status_resubmitted["submission_is_current"] is True


def test_submission_is_scoped_and_ignores_unrelated_completion_rows(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    dept_a = "portal-submission-scope-a"
    dept_b = "portal-submission-scope-b"
    _seed_department(seed_portal_department_data, dept_id=dept_a)
    _seed_department(seed_portal_department_data, dept_id=dept_b)
    _seed_two_day_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=WEEK)
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_a, year=YEAR, week=WEEK, weekday=1, selected_variant="Alt1")
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=dept_a, year=YEAR, week=WEEK, weekday=2, selected_variant="Alt2")

    assert _submit(client_admin, dept_a).status_code == 200
    status_a = _status(_scope(dept_a))
    status_b = _status(_scope(dept_b))
    assert status_a["status"] == "complete"
    assert status_b["status"] == "not_started"
    assert status_b["has_submission"] is False

    db = get_session()
    try:
        group_id = str(uuid.uuid4())
        service_date = f"{YEAR}-10-07"
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_requirement_groups(id, department_id, primary_requirement_id, label, default_quantity, is_active, created_at, updated_at) VALUES(:id, :department_id, NULL, 'Irrelevant', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": group_id, "department_id": dept_b},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO department_requirement_group_completions(group_id, service_date, meal_key, marked) VALUES(:group_id, :service_date, 'lunch', 1)"
            ),
            {"group_id": group_id, "service_date": service_date},
        )
        db.commit()
    finally:
        db.close()

    status_b_after = _status(_scope(dept_b))
    assert status_b_after["status"] == "not_started"
    assert status_b_after["has_submission"] is False