"""Admin department delete route tests for canonical requirement cleanup.

Verifies explicit ownership cleanup for department requirement groups is performed
in the same delete transaction and does not rely on SQLite foreign key cascades.
"""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_department_group(active_site_name: str = "Active Site") -> tuple[str, str, int, str]:
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    diet_repo = DietTypesRepo()
    group_repo = DepartmentRequirementGroupsRepo()

    site, _ = site_repo.create_site(active_site_name)
    department, _ = dept_repo.create_department(
        site_id=site["id"],
        name=f"Department {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    requirement_id = diet_repo.create(
        site_id=site["id"],
        name=f"Requirement {uuid.uuid4()}",
        default_select=False,
        semantics="atomic",
    )
    group = group_repo.create_group(department["id"], 1, [requirement_id], label="Department group")
    return site["id"], department["id"], requirement_id, str(group["id"])


def test_department_delete_cleans_canonical_group_rows_in_same_transaction(app_session, client_admin: FlaskClient) -> None:
    with app_session.app_context():
        site_id, dept_id, requirement_id, group_id = _seed_site_department_group("Delete Site")
        with client_admin.session_transaction() as sess:
            sess["site_id"] = site_id

        response = client_admin.post(
            f"/ui/admin/departments/{dept_id}/delete",
            headers=ADMIN_HEADERS,
            follow_redirects=True,
        )
        assert response.status_code == 200

        from core.db import get_session

        conn = get_session()
        try:
            dept_row = conn.execute(text("SELECT id FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
            group_row = conn.execute(
                text("SELECT id FROM department_requirement_groups WHERE id=:id"),
                {"id": group_id},
            ).fetchone()
            join_row = conn.execute(
                text(
                    "SELECT group_id, dietary_type_id FROM department_requirement_group_requirements "
                    "WHERE group_id=:gid AND dietary_type_id=:did"
                ),
                {"gid": group_id, "did": requirement_id},
            ).fetchone()
            requirement_row = conn.execute(
                text("SELECT id FROM dietary_types WHERE id=:id"),
                {"id": requirement_id},
            ).fetchone()
        finally:
            conn.close()

        assert dept_row is None
        assert group_row is None
        assert join_row is None
        assert requirement_row is not None


def test_department_delete_wrong_site_keeps_department_and_canonical_rows(app_session, client_admin: FlaskClient) -> None:
    with app_session.app_context():
        site_a_id, dept_id, requirement_id, group_id = _seed_site_department_group("Site A")
        site_b, _ = SitesRepo().create_site("Site B")

        with client_admin.session_transaction() as sess:
            sess["site_id"] = site_b["id"]

        response = client_admin.post(
            f"/ui/admin/departments/{dept_id}/delete",
            headers=ADMIN_HEADERS,
            follow_redirects=True,
        )
        assert response.status_code == 200
        html = response.data.decode()
        assert "Avdelning hittades inte för vald site." in html

        from core.db import get_session

        conn = get_session()
        try:
            dept_row = conn.execute(text("SELECT id, site_id FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
            group_row = conn.execute(
                text("SELECT id, department_id FROM department_requirement_groups WHERE id=:id"),
                {"id": group_id},
            ).fetchone()
            join_row = conn.execute(
                text(
                    "SELECT group_id, dietary_type_id FROM department_requirement_group_requirements "
                    "WHERE group_id=:gid AND dietary_type_id=:did"
                ),
                {"gid": group_id, "did": requirement_id},
            ).fetchone()
            requirement_row = conn.execute(
                text("SELECT id FROM dietary_types WHERE id=:id"),
                {"id": requirement_id},
            ).fetchone()
        finally:
            conn.close()

        assert dept_row is not None
        assert str(dept_row[1]) == site_a_id
        assert group_row is not None
        assert join_row is not None
        assert requirement_row is not None


def test_department_delete_cleans_canonical_rows_with_sqlite_fk_off(app_session, client_admin: FlaskClient, monkeypatch) -> None:
    with app_session.app_context():
        site_id, dept_id, requirement_id, group_id = _seed_site_department_group("SQLite Off Site")
        with client_admin.session_transaction() as sess:
            sess["site_id"] = site_id

        from core import ui_blueprint as ui_module
        from core.db import get_session as original_get_session

        def _fk_off_session():
            db = original_get_session()
            db.execute(text("PRAGMA foreign_keys = OFF"))
            pragma_row = db.execute(text("PRAGMA foreign_keys")).fetchone()
            assert int(pragma_row[0] or 0) == 0
            return db

        monkeypatch.setattr(ui_module, "get_session", _fk_off_session)

        response = client_admin.post(
            f"/ui/admin/departments/{dept_id}/delete",
            headers=ADMIN_HEADERS,
            follow_redirects=True,
        )
        assert response.status_code == 200

        conn = original_get_session()
        try:
            dept_row = conn.execute(text("SELECT id FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
            group_row = conn.execute(
                text("SELECT id FROM department_requirement_groups WHERE id=:id"),
                {"id": group_id},
            ).fetchone()
            join_row = conn.execute(
                text(
                    "SELECT group_id, dietary_type_id FROM department_requirement_group_requirements "
                    "WHERE group_id=:gid AND dietary_type_id=:did"
                ),
                {"gid": group_id, "did": requirement_id},
            ).fetchone()
            requirement_row = conn.execute(
                text("SELECT id FROM dietary_types WHERE id=:id"),
                {"id": requirement_id},
            ).fetchone()
        finally:
            conn.close()

        assert dept_row is None
        assert group_row is None
        assert join_row is None
        assert requirement_row is not None