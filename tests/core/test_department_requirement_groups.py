from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.admin_repo import DietTypeDeleteBlockedError
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo


def _seed_department(app_session):
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    site, _ = site_repo.create_site(f"Requirement group site {uuid.uuid4()}")
    department, _ = dept_repo.create_department(
        site_id=site["id"],
        name=f"Requirement group department {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    return site, department


def _seed_atomic_requirements(site_id: str, names: list[str]) -> list[int]:
    repo = DietTypesRepo()
    ids: list[int] = []
    for name in names:
        ids.append(repo.create(site_id=site_id, name=name, default_select=False, semantics="atomic"))
    return ids


def test_atomic_requirement_group_preserves_quantity_and_requirement_count(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_ids = _seed_atomic_requirements(site["id"], ["A"])
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 1, requirement_ids, label="One")

        assert group["default_quantity"] == 1
        assert len(group["requirements"]) == 1
        assert group["requirements"][0]["dietary_type_id"] == requirement_ids[0]
        assert group["requirements"][0]["semantics"] == "atomic"


def test_multi_requirement_group_keeps_quantity_at_one(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_ids = _seed_atomic_requirements(site["id"], ["A", "B"])
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 1, requirement_ids, label="Two requirements")

        assert group["default_quantity"] == 1
        assert len(group["requirements"]) == 2
        assert {item["dietary_type_id"] for item in group["requirements"]} == set(requirement_ids)


def test_quantity_conservation_across_groups(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        a_id, b_id, c_id = _seed_atomic_requirements(site["id"], ["A", "B", "C"])
        repo = DepartmentRequirementGroupsRepo()

        repo.create_group(department["id"], 1, [a_id, b_id], label="Group 1")
        repo.create_group(department["id"], 2, [c_id], label="Group 2")

        groups = repo.list_for_department(department["id"])
        assert sum(int(group["default_quantity"]) for group in groups) == 3
        assert sum(len(group["requirements"]) for group in groups) == 3


def test_duplicate_requirement_is_rejected(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_id = _seed_atomic_requirements(site["id"], ["A"])[0]
        repo = DepartmentRequirementGroupsRepo()

        with pytest.raises(ValueError, match="duplicate_requirement_id"):
            repo.create_group(department["id"], 1, [requirement_id, requirement_id], label="Dup")


def test_non_atomic_and_combined_legacy_bucket_requirements_are_rejected(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        atomic_id = _seed_atomic_requirements(site["id"], ["Atomic A"])[0]
        legacy_bucket_id = DietTypesRepo().create(
            site_id=site["id"],
            name="Laktos och gluten",
            default_select=False,
        )
        repo = DepartmentRequirementGroupsRepo()

        with pytest.raises(ValueError, match="dietary_type_not_atomic"):
            repo.create_group(department["id"], 1, [legacy_bucket_id], label="Legacy")

        with pytest.raises(ValueError, match="duplicate_requirement_id"):
            repo.create_group(department["id"], 1, [atomic_id, atomic_id], label="Dup atomic")


def test_cross_site_and_null_site_requirements_are_rejected(app_session) -> None:
    with app_session.app_context():
        site_a, department_a = _seed_department(app_session)
        site_b, _department_b = _seed_department(app_session)
        requirement_a = _seed_atomic_requirements(site_a["id"], ["A"])[0]
        requirement_b = _seed_atomic_requirements(site_b["id"], ["B"])[0]
        orphan_requirement = DietTypesRepo().create(
            site_id=None,
            name=f"Orphan atomic {uuid.uuid4()}",
            default_select=False,
            semantics="atomic",
        )
        repo = DepartmentRequirementGroupsRepo()

        with pytest.raises(ValueError, match="dietary_type_site_mismatch"):
            repo.create_group(department_a["id"], 1, [requirement_b], label="Cross site")

        with pytest.raises(ValueError, match="dietary_type_site_missing"):
            repo.create_group(department_a["id"], 1, [orphan_requirement], label="Null site")

        group = repo.create_group(department_a["id"], 1, [requirement_a], label="Site A")
        assert group["requirements"][0]["dietary_type_id"] == requirement_a


def test_atomic_requirement_without_requirement_key_is_rejected(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, 'Keyless atomic', 'Övrigt', NULL, 'atomic', 0)"
                ),
                {"site_id": site["id"]},
            )
            db.commit()
            requirement_id = int(
                db.execute(text("SELECT id FROM dietary_types WHERE name='Keyless atomic'"))
                .fetchone()[0]
            )
        finally:
            db.close()

        repo = DepartmentRequirementGroupsRepo()
        with pytest.raises(ValueError, match="dietary_type_requirement_key_missing"):
            repo.create_group(department["id"], 1, [requirement_id], label="Missing key")


def test_missing_department_and_missing_dietary_type_are_rejected(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_id = _seed_atomic_requirements(site["id"], ["A"])[0]
        repo = DepartmentRequirementGroupsRepo()
        missing_department_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="department_not_found"):
            repo.create_group(missing_department_id, 1, [requirement_id], label="Missing dept")

        with pytest.raises(ValueError, match="dietary_type_not_found"):
            repo.create_group(department["id"], 1, [99999999], label="Missing req")


def test_negative_quantity_is_rejected(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_id = _seed_atomic_requirements(site["id"], ["A"])[0]
        repo = DepartmentRequirementGroupsRepo()

        with pytest.raises(ValueError, match="default_quantity_negative"):
            repo.create_group(department["id"], -1, [requirement_id], label="Negative")


def test_replace_requirements_is_atomic(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        a_id, b_id = _seed_atomic_requirements(site["id"], ["A", "B"])
        repo = DepartmentRequirementGroupsRepo()
        group = repo.create_group(department["id"], 1, [a_id], label="Replace me")
        group_id = str(group["id"])

        with pytest.raises(ValueError, match="dietary_type_not_found"):
            repo.replace_requirements(group_id, [b_id, 99999999])

        reread = repo.get_group(group_id)
        assert reread is not None
        assert [item["dietary_type_id"] for item in reread["requirements"]] == [a_id]

        updated = repo.replace_requirements(group_id, [b_id])
        assert updated is not None
        assert [item["dietary_type_id"] for item in updated["requirements"]] == [b_id]


def test_rename_stability_and_active_toggle(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        a_id, b_id = _seed_atomic_requirements(site["id"], ["A", "B"])
        repo = DepartmentRequirementGroupsRepo()
        created = repo.create_group(department["id"], 2, [a_id, b_id], label="Original")
        group_id = str(created["id"])

        updated = repo.update_group(group_id, label="Renamed", default_quantity=2, is_active=False)
        assert updated is not None
        assert updated["id"] == group_id
        assert updated["label"] == "Renamed"
        assert updated["default_quantity"] == 2
        assert updated["is_active"] is False
        assert {item["dietary_type_id"] for item in updated["requirements"]} == {a_id, b_id}

        reactivated = repo.update_group(group_id, is_active=True)
        assert reactivated is not None
        assert reactivated["id"] == group_id
        assert reactivated["is_active"] is True
        assert {item["dietary_type_id"] for item in reactivated["requirements"]} == {a_id, b_id}


def test_deterministic_reads(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        a_id, b_id = _seed_atomic_requirements(site["id"], ["A", "B"])
        repo = DepartmentRequirementGroupsRepo()
        group = repo.create_group(department["id"], 1, [b_id, a_id], label="Deterministic")
        group_id = str(group["id"])

        first = repo.get_group(group_id)
        second = repo.get_group(group_id)
        assert first is not None and second is not None
        assert [item["dietary_type_id"] for item in first["requirements"]] == [
            item["dietary_type_id"] for item in second["requirements"]
        ]
        assert first["requirements"] == second["requirements"]


def test_canonical_requirement_delete_is_blocked_when_group_references_it(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        requirement_id = _seed_atomic_requirements(site["id"], ["A"])[0]
        group_repo = DepartmentRequirementGroupsRepo()
        group = group_repo.create_group(department["id"], 1, [requirement_id], label="Blocked")

        diet_repo = DietTypesRepo()
        with pytest.raises(DietTypeDeleteBlockedError) as excinfo:
            diet_repo.delete(requirement_id)

        assert "department_requirement_group_requirements" in str(excinfo.value)

        db = get_session()
        try:
            diet_row = db.execute(text("SELECT id FROM dietary_types WHERE id=:id"), {"id": requirement_id}).fetchone()
            group_row = db.execute(
                text("SELECT id, default_quantity FROM department_requirement_groups WHERE id=:id"),
                {"id": group["id"]},
            ).fetchone()
            rel_row = db.execute(
                text("SELECT group_id, dietary_type_id FROM department_requirement_group_requirements WHERE group_id=:gid AND dietary_type_id=:did"),
                {"gid": group["id"], "did": requirement_id},
            ).fetchone()
        finally:
            db.close()

        assert diet_row is not None
        assert group_row is not None
        assert int(group_row[1]) == 1
        assert rel_row is not None


def test_unused_atomic_requirement_can_still_be_deleted(app_session) -> None:
    with app_session.app_context():
        site, _department = _seed_department(app_session)
        requirement_id = _seed_atomic_requirements(site["id"], ["Unused"])[0]
        diet_repo = DietTypesRepo()

        diet_repo.delete(requirement_id)

        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM dietary_types WHERE id=:id"), {"id": requirement_id}).fetchone()
        finally:
            db.close()

        assert row is None


def test_cleanup_invalid_all_skips_referenced_canonical_requirement(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(app_session)
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, ' ', 'Övrigt', 'legacy_777', 'atomic', 0)"
                ),
                {"site_id": site["id"]},
            )
            db.commit()
            requirement_id = int(
                db.execute(text("SELECT id FROM dietary_types WHERE requirement_key='legacy_777'"))
                .fetchone()[0]
            )
        finally:
            db.close()

        group_repo = DepartmentRequirementGroupsRepo()
        group = group_repo.create_group(department["id"], 1, [requirement_id], label="Cleanup guard")
        diet_repo = DietTypesRepo()

        deleted = diet_repo.cleanup_invalid_all()
        assert requirement_id not in deleted

        db = get_session()
        try:
            diet_row = db.execute(text("SELECT id FROM dietary_types WHERE id=:id"), {"id": requirement_id}).fetchone()
            rel_row = db.execute(
                text("SELECT group_id, dietary_type_id FROM department_requirement_group_requirements WHERE group_id=:gid AND dietary_type_id=:did"),
                {"gid": group["id"], "did": requirement_id},
            ).fetchone()
            group_row = db.execute(text("SELECT id FROM department_requirement_groups WHERE id=:id"), {"id": group["id"]}).fetchone()
        finally:
            db.close()

        assert diet_row is not None
        assert rel_row is not None
        assert group_row is not None
