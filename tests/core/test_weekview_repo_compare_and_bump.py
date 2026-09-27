from __future__ import annotations

from sqlalchemy import text

from core.db import get_session
from core.weekview.repo import WeekviewRepo


def _seed_version_row(tenant_id: int, department_id: str, year: int, week: int, version: int) -> None:
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


def _read_version(tenant_id: int, department_id: str, year: int, week: int) -> int | None:
    db = get_session()
    try:
        row = db.execute(
            text(
                """
                SELECT version
                FROM weekview_versions
                WHERE tenant_id=:tenant_id AND department_id=:department_id AND year=:year AND week=:week
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "department_id": department_id,
                "year": year,
                "week": week,
            },
        ).fetchone()
        return None if row is None else int(row[0])
    finally:
        db.close()


def test_compare_and_bump_initializes_missing_row_and_get_version_remains_unchanged(app_session) -> None:
    repo = WeekviewRepo()
    tenant_id = 11
    department_id = "dept-init"
    year = 2026
    week = 39

    with app_session.app_context():
        assert repo.get_version(tenant_id, year, week, department_id) == 0
        bumped = repo.compare_and_bump_version(tenant_id, year, week, department_id, expected_version=0)

    assert bumped == 1
    assert _read_version(tenant_id, department_id, year, week) == 1
    with app_session.app_context():
        assert repo.get_version(tenant_id, year, week, department_id) == 1


def test_compare_and_bump_rejects_stale_expected_version_without_incrementing(app_session) -> None:
    repo = WeekviewRepo()
    tenant_id = 12
    department_id = "dept-stale"
    year = 2026
    week = 40

    _seed_version_row(tenant_id, department_id, year, week, 0)

    with app_session.app_context():
        first = repo.compare_and_bump_version(tenant_id, year, week, department_id, expected_version=0)
        stale = repo.compare_and_bump_version(tenant_id, year, week, department_id, expected_version=0)

    assert first == 1
    assert stale is None
    assert _read_version(tenant_id, department_id, year, week) == 1


def test_compare_and_bump_allows_current_version_and_isolates_tenant_department_and_week(app_session) -> None:
    repo = WeekviewRepo()
    tenant_a = 21
    tenant_b = 22
    dep_a = "dept-a"
    dep_b = "dept-b"
    year = 2026
    week_a = 41
    week_b = 42

    _seed_version_row(tenant_a, dep_a, year, week_a, 1)
    _seed_version_row(tenant_a, dep_a, year, week_b, 7)
    _seed_version_row(tenant_a, dep_b, year, week_a, 4)
    _seed_version_row(tenant_b, dep_a, year, week_a, 9)

    with app_session.app_context():
        bumped = repo.compare_and_bump_version(tenant_a, year, week_a, dep_a, expected_version=1)

    assert bumped == 2
    assert _read_version(tenant_a, dep_a, year, week_a) == 2
    assert _read_version(tenant_a, dep_a, year, week_b) == 7
    assert _read_version(tenant_a, dep_b, year, week_a) == 4
    assert _read_version(tenant_b, dep_a, year, week_a) == 9


def test_compare_and_bump_missing_row_then_stale_attempt_returns_none(app_session) -> None:
    repo = WeekviewRepo()
    tenant_id = 31
    department_id = "dept-fresh"
    year = 2026
    week = 43

    with app_session.app_context():
        first = repo.compare_and_bump_version(tenant_id, year, week, department_id, expected_version=0)
        stale = repo.compare_and_bump_version(tenant_id, year, week, department_id, expected_version=0)

    assert first == 1
    assert stale is None
    assert _read_version(tenant_id, department_id, year, week) == 1