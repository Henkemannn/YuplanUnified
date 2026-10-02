from __future__ import annotations

import json
from hashlib import sha1

from core.commun_builder_publication import CommunBuilderPublicationService
from core.department_portal_week_submission_repo import DepartmentPortalWeekSubmissionRepo
from portal.department.auth import DepartmentPortalScope
from portal.department.models import PortalWeekSubmissionStatus
from portal.department.service import build_department_week_payload


def _required_choice_signature(days: list[dict]) -> tuple[int, int, str]:
    required_entries: list[dict[str, object]] = []
    completed_count = 0
    for index, day in enumerate(days, start=1):
        menu = day.get("menu") or {}
        if not menu.get("lunch_alt1") or not menu.get("lunch_alt2"):
            continue
        selected_alt = day.get("choice", {}).get("selected_alt")
        normalized_alt = selected_alt if selected_alt in {"Alt1", "Alt2"} else None
        if normalized_alt is not None:
            completed_count += 1
        required_entries.append({"weekday": index, "selected_alt": normalized_alt})
    payload = json.dumps(required_entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return len(required_entries), completed_count, sha1(payload.encode("utf-8")).hexdigest()


class DepartmentPortalWeekSubmissionService:
    def __init__(self, *, repo: DepartmentPortalWeekSubmissionRepo | None = None) -> None:
        self._repo = repo or DepartmentPortalWeekSubmissionRepo()

    def _load_current_state(self, scope: DepartmentPortalScope, year: int, week: int) -> tuple[dict, dict, object]:
        publication = CommunBuilderPublicationService().get_publication_for_week(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            year=year,
            week=week,
        )
        if publication is None:
            raise ValueError("publication_missing")
        payload = build_department_week_payload(scope, year, week)
        required_choice_count, completed_choice_count, current_choice_signature = _required_choice_signature(payload["days"])
        submission = self._repo.get_for_week(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            department_id=scope.department_id,
            year=year,
            week=week,
        )
        return (
            {
                "tenant_id": scope.tenant_id,
                "site_id": scope.site_id,
                "department_id": scope.department_id,
                "year": year,
                "week": week,
                "publication_builder_menu_id": str(publication.builder_menu_id),
                "publication_builder_menu_version": int(publication.builder_menu_version),
                "required_choice_count": required_choice_count,
                "completed_choice_count": completed_choice_count,
                "current_choice_signature": current_choice_signature,
            },
            payload,
            submission,
        )

    def get_status(self, scope: DepartmentPortalScope, year: int, week: int) -> PortalWeekSubmissionStatus:
        state, _payload, submission = self._load_current_state(scope, year, week)
        has_submission = submission is not None
        submission_is_current = bool(
            submission
            and str(submission.get("builder_menu_id") or "") == str(state["publication_builder_menu_id"])
            and int(submission.get("builder_menu_version") or 0) == int(state["publication_builder_menu_version"])
            and str(submission.get("choice_signature") or "") == str(state["current_choice_signature"])
        )
        needs_review = has_submission and not submission_is_current
        is_submittable = int(state["completed_choice_count"]) == int(state["required_choice_count"])
        if submission_is_current:
            status = "complete"
        elif has_submission:
            status = "in_progress"
        elif int(state["completed_choice_count"]) == 0:
            status = "not_started"
        else:
            status = "in_progress"
        return {
            "tenant_id": int(state["tenant_id"]),
            "site_id": str(state["site_id"]),
            "department_id": str(state["department_id"]),
            "year": int(state["year"]),
            "week": int(state["week"]),
            "publication_builder_menu_id": str(state["publication_builder_menu_id"]),
            "publication_builder_menu_version": int(state["publication_builder_menu_version"]),
            "required_choice_count": int(state["required_choice_count"]),
            "completed_choice_count": int(state["completed_choice_count"]),
            "has_submission": has_submission,
            "submission_is_current": submission_is_current,
            "needs_review": bool(needs_review),
            "is_submittable": bool(is_submittable),
            "status": status,
        }

    def submit(self, scope: DepartmentPortalScope, year: int, week: int) -> PortalWeekSubmissionStatus:
        state, _payload, _submission = self._load_current_state(scope, year, week)
        if int(state["completed_choice_count"]) != int(state["required_choice_count"]):
            raise ValueError("portal_week_not_submittable")
        self._repo.upsert_for_week(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            department_id=scope.department_id,
            year=year,
            week=week,
            builder_menu_id=str(state["publication_builder_menu_id"]),
            builder_menu_version=int(state["publication_builder_menu_version"]),
            choice_signature=str(state["current_choice_signature"]),
        )
        return self.get_status(scope, year, week)